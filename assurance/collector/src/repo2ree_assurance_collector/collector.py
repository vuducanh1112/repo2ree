"""Write evidence fetched through the control plane into a dossier, one source at a time.

Collection never raises for a source it could not get: the source is listed
with its problem, so the checker reports the gap instead of judging around it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_assurance_collector.client import ControlPlane, UnreachableError
from repo2ree_assurance_dossier import (
    Cut,
    Dossier,
    DossierContext,
    DossierSource,
    read_dossier,
    write_dossier,
)

JOURNAL = "journal"
STORES = "stores"
TELEMETRY = "telemetry"
JOURNALS = "/api/v1/behaviour/journals"
# An owner's journal epoch, as the runtime names it: ``<process>-<epoch>.ndjson``.
JOURNAL_FILE = re.compile(r"^[a-z][a-z0-9-]*-[0-9]{6}\.ndjson$")
STATE = "/api/v1/behaviour/state"
ARCHIVES = "/api/v1/behaviour/archives"


def start(
    directory: Path,
    *,
    control_plane: str | None = None,
    suite: str | None = None,
    test: str | None = None,
    build_revision: str | None = None,
) -> None:
    """Begin a dossier; it lists nothing until sources are collected into it."""
    context = DossierContext(suite=suite, test=test, started=time.time())
    dossier = Dossier(control_plane=control_plane, build_revision=build_revision, context=context)
    write_dossier(directory, dossier)


def _add(directory: Path, source: DossierSource) -> DossierSource:
    write_dossier(directory, read_dossier(directory).with_source(source))
    return source


def _failed(source: DossierSource, problem: str) -> DossierSource:
    return source.model_copy(update={"status": "error", "problem": problem})


# ================================================
# REEs, as the product downloads them
# ================================================


def archive(directory: Path, path: Path, *, cut: Cut | None, origin: str, name: str | None = None) -> DossierSource:
    """Record a downloaded REE archive with the cut it was built at."""
    name = name or path.stem
    source = DossierSource(kind="git", path=f"rees/{name}/ree", origin=origin, name=name, cut=cut)
    destination = directory / "rees" / name
    try:
        extract(path, destination)
        if not (destination / "ree" / ".git").is_dir():
            raise ValueError("the archive holds no REE repository")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        source = _failed(source, str(exc))
    return _add(directory, source)


def served_archives(control_plane: ControlPlane) -> dict[str, dict[str, Any]]:
    """The archives the control plane served, by the digest of their bytes."""
    return {served["sha256"]: served for served in control_plane.get_json(ARCHIVES)["archives"]}


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            hashed.update(chunk)
    return hashed.hexdigest()


def _served_copy(directory: Path, control_plane: ControlPlane, path: Path, served: dict[str, Any]) -> DossierSource:
    ree_id = str(served["ree_id"])
    name = ree_id if not (directory / "rees" / ree_id).exists() else f"{ree_id}-{served['sha256'][:12]}"
    cut = {journal: (int(low), int(high)) for journal, (low, high) in served["cut"].items()}
    origin = control_plane.address(f"/api/v1/rees/{ree_id}/ree-archive")
    return archive(directory, path, cut=cut, origin=origin, name=name)


def kept_archives(directory: Path, control_plane: ControlPlane, folders: list[Path]) -> list[DossierSource]:
    """REE archives a client downloaded and kept, placed by the control plane's record of serving them.

    A zip the control plane did not serve (another run's, a browser trace) is not evidence of this
    deployment and is passed over.
    """
    try:
        served = served_archives(control_plane)
    except UnreachableError as exc:
        failed = DossierSource(kind="git", path="rees", origin=control_plane.address(ARCHIVES))
        return [_add(directory, _failed(failed, str(exc)))]
    found = sorted({path for folder in folders if folder.is_dir() for path in folder.rglob("*.zip")})
    copies: dict[str, Path] = {}
    for path in found:
        # One source per archive served: a client may keep several copies (a report attachment).
        if (sha := digest(path)) in served:
            copies.setdefault(sha, path)
    return [_served_copy(directory, control_plane, path, served[sha]) for sha, path in copies.items()]


def download_archive(directory: Path, control_plane: ControlPlane, ree_id: str) -> DossierSource:
    """Download an REE through the control plane, as its owner would, and record it with its cut."""
    path = f"/api/v1/rees/{ree_id}/ree-archive"
    failed = DossierSource(kind="git", path=f"rees/{ree_id}/ree", origin=control_plane.address(path), name=ree_id)
    target = directory / "downloads" / f"{ree_id}.zip"
    try:
        control_plane.download(path, target)
        served = served_archives(control_plane).get(digest(target))
    except UnreachableError as exc:
        return _add(directory, _failed(failed, str(exc)))
    try:
        if served is None:
            return _add(directory, _failed(failed, "the control plane has no record of serving this archive"))
        return _served_copy(directory, control_plane, target, served)
    finally:
        target.unlink(missing_ok=True)


def extract(path: Path, destination: Path) -> None:
    """Unpack an REE archive, keeping its symlinks, never writing outside ``destination``."""
    with zipfile.ZipFile(path) as bundle:
        for info in bundle.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe archive member {info.filename}")
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if stat.S_ISLNK(info.external_attr >> 16):
                target.symlink_to(bundle.read(info).decode())
            else:
                with bundle.open(info) as member, target.open("wb") as output:
                    shutil.copyfileobj(member, output, 1 << 20)


# ================================================
# The owners' journals and persisted state
# ================================================


def describe(directory: Path, control_plane: ControlPlane) -> None:
    """Name the deployment the dossier was collected from: its control plane and build."""
    dossier = read_dossier(directory)
    if dossier.build_revision is None:
        try:
            revision = control_plane.get_json("/api/v1/system/build-info").get("revision") or None
        except UnreachableError:
            revision = None
        dossier = dossier.model_copy(update={"build_revision": revision})
    write_dossier(directory, dossier.model_copy(update={"control_plane": control_plane.url}))


def collect_control_plane(directory: Path, control_plane: ControlPlane) -> list[DossierSource]:
    """The owners' persisted state, then their journals, so the journals reach past the state's cut."""
    describe(directory, control_plane)
    return [_state(directory, control_plane), _journals(directory, control_plane)]


def _state(directory: Path, control_plane: ControlPlane) -> DossierSource:
    source = DossierSource(kind="state", path=STORES, origin=control_plane.address(STATE), name="api")
    try:
        state = control_plane.get_json(STATE)
    except UnreachableError as exc:
        return _add(directory, _failed(source, str(exc)))
    stores = directory / STORES
    for name, document in state["runs"].items():
        target = stores / "runs" / name / "state.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2))
    stores.mkdir(parents=True, exist_ok=True)
    if state["allocations"] is not None:
        (stores / "allocations.json").write_text(json.dumps(state["allocations"], indent=2))
    cut = {journal: (int(low), int(high)) for journal, (low, high) in state["cut"].items()}
    return _add(directory, source.model_copy(update={"cut": cut}))


def _journals(directory: Path, control_plane: ControlPlane) -> DossierSource:
    source = DossierSource(kind="journal", path=JOURNAL, origin=control_plane.address(JOURNALS), name="api")
    target = directory / JOURNAL
    target.mkdir(parents=True, exist_ok=True)
    try:
        for journal in control_plane.get_json(JOURNALS)["journals"]:
            (target / f"{journal['id']}.ndjson").write_bytes(control_plane.get_bytes(f"{JOURNALS}/{journal['id']}"))
    except UnreachableError as exc:
        return _add(directory, _failed(source, str(exc)))
    return _add(directory, source)


def stopped_owners(
    directory: Path, *, journals: Path, runs: Path | None, allocations: Path | None
) -> list[DossierSource]:
    """The owners' journals and persisted state, exported after they stopped.

    Only after its owner stops does a journal carry its close, and only a close gives
    "eventually" a horizon, so this is the evidence a deployment that is shutting down for
    good can give. Taken after the owners stopped, the state carries no cut and must match
    the journals exactly. It replaces whatever was collected through the control plane.
    """
    journal = DossierSource(kind="journal", path=JOURNAL, origin=f"{journals} (after its owners stopped)", name="api")
    target = directory / JOURNAL
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    try:
        # Only the owners' journals: the directory also keeps the control plane's record of serving archives.
        found = sorted(path for path in journals.glob("*.ndjson") if JOURNAL_FILE.match(path.name))
        if not found:
            raise FileNotFoundError(f"no journals in {journals}")
        for path in found:
            shutil.copyfile(path, target / path.name)
    except OSError as exc:
        journal = _failed(journal, str(exc))
    recorded = [_add(directory, journal)]
    if runs is None and allocations is None:
        return recorded
    origins = ", ".join(str(path) for path in (runs, allocations) if path is not None)
    state = DossierSource(kind="state", path=STORES, origin=f"{origins} (after their owners stopped)", name="api")
    stores = directory / STORES
    shutil.rmtree(stores, ignore_errors=True)
    stores.mkdir(parents=True)
    try:
        for run in sorted(runs.glob("*/state.json")) if runs is not None else []:
            (stores / "runs" / run.parent.name).mkdir(parents=True)
            shutil.copyfile(run, stores / "runs" / run.parent.name / "state.json")
        if allocations is not None and allocations.is_file():
            shutil.copyfile(allocations, stores / "allocations.json")
    except OSError as exc:
        state = _failed(state, str(exc))
    return [*recorded, _add(directory, state)]


# ================================================
# Spans and the dossier's context
# ================================================


def spans(directory: Path, files: list[Path], origin: str) -> list[DossierSource]:
    """List span files, copying in those that live outside the dossier."""
    recorded: list[DossierSource] = []
    for path in files:
        if not path.is_file():
            continue
        inside = path.resolve().is_relative_to(directory.resolve())
        if not inside:
            (directory / TELEMETRY).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, directory / TELEMETRY / path.name)
        relative = path.resolve().relative_to(directory.resolve()) if inside else Path(TELEMETRY, path.name)
        source = DossierSource(kind="spans", path=relative.as_posix(), origin=origin, name=path.stem)
        recorded.append(_add(directory, source))
    return recorded


def finish(directory: Path, outcome: str | None = None) -> None:
    dossier = read_dossier(directory)
    context = dossier.context.model_copy(update={"outcome": outcome, "finished": time.time()})
    write_dossier(directory, dossier.model_copy(update={"context": context}))
