"""Write evidence fetched through the control plane into a dossier, one source at a time.

Every source ends up listed in the manifest: recorded, or with what went wrong (``_collect``), so
the checker reports a gap instead of judging around it. A source's files are written to a
staging folder and moved into place only once complete, and the manifest is updated after each
source, so an interrupted collection still lists what it finished and nothing it did not.
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import re
import shutil
import stat
import tempfile
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import IO

from repo2ree_assurance_collector.client import (
    SAFE_NAME,
    BuildInfo,
    ControlPlane,
    ControlPlaneError,
    Journals,
    OwnerState,
    ServedArchive,
    ServedArchives,
)
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
REES = "rees"
TELEMETRY = "telemetry"
BUILD_INFO = "/api/v1/system/build-info"
JOURNALS = "/api/v1/behaviour/journals"
STATE = "/api/v1/behaviour/state"
ARCHIVES = "/api/v1/behaviour/archives"
# An owner's journal epoch, as the runtime names it: ``<process>-<epoch>.ndjson``.
JOURNAL_FILE = re.compile(r"^[a-z][a-z0-9-]*-[0-9]{6}\.ndjson$")

# What collecting one source can run into. Anything else is a bug in the collector, not a gap in
# the evidence, and is raised.
GAPS = (ControlPlaneError, OSError, ValueError, zipfile.BadZipFile)


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


def _list(directory: Path, source: DossierSource) -> DossierSource:
    write_dossier(directory, read_dossier(directory).with_source(source))
    return source


def _failed(source: DossierSource, problem: object) -> DossierSource:
    return source.model_copy(update={"status": "error", "problem": str(problem)})


def _collect(directory: Path, source: DossierSource, gather: Callable[[], DossierSource]) -> DossierSource:
    """Collect one source and list it either way: as gathered, or failed with the reason."""
    try:
        gathered = gather()
    except GAPS as exc:
        return _list(directory, _failed(source, exc))
    return _list(directory, gathered)


@contextmanager
def _staged(directory: Path, relative: str) -> Iterator[Path]:
    """A fresh folder that replaces ``directory/relative`` only once everything was written to it."""
    final = directory / relative
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{final.name}-", dir=final.parent))
    try:
        yield staging
        shutil.rmtree(final, ignore_errors=True)
        staging.rename(final)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# ================================================
# REEs, as the product downloads them
# ================================================


def unpack_archive(directory: Path, path: Path, *, cut: Cut | None, origin: str, name: str) -> DossierSource:
    """Unpack a downloaded REE archive into the dossier, listed with the cut it was built at."""
    source = DossierSource(kind="git", path=f"{REES}/{name}/ree", origin=origin, name=name, cut=cut)

    def gather() -> DossierSource:
        with _staged(directory, f"{REES}/{name}") as staging:
            extract(path, staging)
            if not (staging / "ree" / ".git").is_dir():
                raise ValueError("the archive holds no REE repository")
        return source

    return _collect(directory, source, gather)


def _served_archives(control_plane: ControlPlane) -> dict[str, ServedArchive]:
    """The archives the control plane served, by the digest of their bytes."""
    return {served.sha256: served for served in control_plane.get(ServedArchives, ARCHIVES).archives}


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            hashed.update(chunk)
    return hashed.hexdigest()


def _served_copy(directory: Path, control_plane: ControlPlane, path: Path, served: ServedArchive) -> DossierSource:
    taken = (directory / REES / served.ree_id).exists()
    name = f"{served.ree_id}-{served.sha256[:12]}" if taken else served.ree_id
    origin = control_plane.address(f"/api/v1/rees/{served.ree_id}/ree-archive")
    return unpack_archive(directory, path, cut=served.cut, origin=origin, name=name)


def kept_archives(directory: Path, control_plane: ControlPlane, folders: list[Path]) -> list[DossierSource]:
    """REE archives a client downloaded and kept, placed by the control plane's record of serving them.

    A zip the control plane did not serve (another run's, a browser trace) is not evidence of this
    deployment and is passed over.
    """
    try:
        served = _served_archives(control_plane)
    except ControlPlaneError as exc:
        failed = DossierSource(kind="git", path=REES, origin=control_plane.address(ARCHIVES))
        return [_list(directory, _failed(failed, exc))]
    found = sorted({path for folder in folders if folder.is_dir() for path in folder.rglob("*.zip")})
    copies: dict[str, Path] = {}
    for path in found:
        # One source per archive served: a client may keep several copies (a report attachment).
        if (sha := digest(path)) in served:
            copies.setdefault(sha, path)
    return [_served_copy(directory, control_plane, path, served[sha]) for sha, path in copies.items()]


def download_archive(directory: Path, control_plane: ControlPlane, ree_id: str) -> DossierSource:
    """Download an REE through the control plane, as its owner would, and list it with its cut."""
    path = f"/api/v1/rees/{ree_id}/ree-archive"
    source = DossierSource(kind="git", path=f"{REES}/{ree_id}/ree", origin=control_plane.address(path), name=ree_id)
    if not SAFE_NAME.fullmatch(ree_id):
        return _list(directory, _failed(source.model_copy(update={"path": REES}), f"not an REE id: {ree_id!r}"))
    with tempfile.TemporaryDirectory(dir=directory) as scratch:
        target = Path(scratch) / f"{ree_id}.zip"
        try:
            control_plane.download(path, target)
            served = _served_archives(control_plane).get(digest(target))
        except ControlPlaneError as exc:
            return _list(directory, _failed(source, exc))
        if served is None:
            return _list(directory, _failed(source, "the control plane has no record of serving this archive"))
        return _served_copy(directory, control_plane, target, served)


# Where a REE keeps its Git LFS payloads, and how it marks a path as one (repo2ree_core's capture
# controls write one exact, JSON-quoted path per line).
_LFS_OBJECTS = "ree/.git/lfs/objects/"
_LFS_ATTRIBUTE = re.compile(r'^("(?:[^"\\]|\\.)*")\s.*\bfilter=lfs\b', re.MULTILINE)


def _lfs_paths(bundle: zipfile.ZipFile) -> frozenset[str]:
    """The archive members the REE stores in Git LFS, from its ``.gitattributes``."""
    try:
        attributes = bundle.read("ree/.gitattributes").decode()
    except KeyError:
        return frozenset()
    return frozenset(f"ree{json.loads(quoted)}" for quoted in _LFS_ATTRIBUTE.findall(attributes))


def _lfs_pointer(member: IO[bytes]) -> bytes:
    """The Git LFS pointer of a payload: what the REE's history commits in its place."""
    hashed = hashlib.sha256()
    size = 0
    while chunk := member.read(1 << 20):
        hashed.update(chunk)
        size += len(chunk)
    return f"version https://git-lfs.github.com/spec/v1\noid sha256:{hashed.hexdigest()}\nsize {size}\n".encode()


def extract(path: Path, destination: Path) -> None:
    """Unpack an REE archive as evidence, keeping its symlinks as links, never writing outside ``destination``.

    A link may point anywhere (a venv's interpreter does) and is never followed: a member under a
    link the archive itself created, or at one, is refused, since writing it would go wherever the
    link points.

    LFS payloads stay out (a runtime image can be gigabytes, copied at every collection and every
    fetch of a run): the payload store is skipped, and each file the REE keeps in LFS is written
    as the pointer its history commits. What the checker reads, the history and the operation
    records, is complete without them; the payloads remain in the archive the test kept.
    """
    with zipfile.ZipFile(path) as bundle:
        lfs = _lfs_paths(bundle)
        for info in bundle.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe archive member {info.filename}")
            if info.filename.startswith(_LFS_OBJECTS):
                continue
            parts = relative.parts
            if any(destination.joinpath(*parts[:depth]).is_symlink() for depth in range(1, len(parts) + 1)):
                raise ValueError(f"archive member {info.filename} lies under a link the archive made")
            target = destination.joinpath(*parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if stat.S_ISLNK(info.external_attr >> 16):
                target.symlink_to(bundle.read(info).decode())
            elif relative.as_posix() in lfs:
                with bundle.open(info) as member:
                    target.write_bytes(_lfs_pointer(member))
            else:
                with bundle.open(info) as member, target.open("wb") as output:
                    shutil.copyfileobj(member, output, 1 << 20)


# ================================================
# The owners' journals and persisted state
# ================================================


def record_deployment(directory: Path, control_plane: ControlPlane) -> None:
    """Name the deployment the dossier was collected from: its control plane and, if it says, its build."""
    dossier = read_dossier(directory)
    if dossier.build_revision is None:
        try:
            revision = control_plane.get(BuildInfo, BUILD_INFO).revision
        except ControlPlaneError:
            revision = None
        dossier = dossier.model_copy(update={"build_revision": revision})
    write_dossier(directory, dossier.model_copy(update={"control_plane": control_plane.url}))


def collect_control_plane(directory: Path, control_plane: ControlPlane) -> list[DossierSource]:
    """The owners' persisted state, then their journals, so the journals reach past the state's cut."""
    record_deployment(directory, control_plane)
    return [_state(directory, control_plane), _journals(directory, control_plane)]


def _state(directory: Path, control_plane: ControlPlane) -> DossierSource:
    source = DossierSource(kind="state", path=STORES, origin=control_plane.address(STATE), name="api")

    def gather() -> DossierSource:
        state = control_plane.get(OwnerState, STATE)
        with _staged(directory, STORES) as stores:
            for name, document in state.runs.items():
                (stores / "runs" / name).mkdir(parents=True)
                (stores / "runs" / name / "state.json").write_text(json.dumps(document, indent=2))
            if state.allocations is not None:
                (stores / "allocations.json").write_text(json.dumps(state.allocations, indent=2))
        return source.model_copy(update={"cut": state.cut})

    return _collect(directory, source, gather)


def _journals(directory: Path, control_plane: ControlPlane) -> DossierSource:
    source = DossierSource(kind="journal", path=JOURNAL, origin=control_plane.address(JOURNALS), name="api")

    def gather() -> DossierSource:
        listed = control_plane.get(Journals, JOURNALS)
        with _staged(directory, JOURNAL) as journals:
            for journal in listed.journals:
                body = control_plane.get_bytes(f"{JOURNALS}/{journal.id}")
                (journals / f"{journal.id}.ndjson").write_bytes(body)
        return source

    return _collect(directory, source, gather)


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

    def copy_journals() -> DossierSource:
        # Only the owners' journals: the directory also keeps the control plane's record of serving archives.
        found = sorted(path for path in journals.glob("*.ndjson") if JOURNAL_FILE.match(path.name))
        if not found:
            raise FileNotFoundError(f"no journals in {journals}")
        with _staged(directory, JOURNAL) as target:
            for path in found:
                shutil.copyfile(path, target / path.name)
        return journal

    listed = [_collect(directory, journal, copy_journals)]
    if runs is None and allocations is None:
        return listed
    origins = ", ".join(str(path) for path in (runs, allocations) if path is not None)
    state = DossierSource(kind="state", path=STORES, origin=f"{origins} (after their owners stopped)", name="api")

    def copy_stores() -> DossierSource:
        with _staged(directory, STORES) as stores:
            for run in sorted(runs.glob("*/state.json")) if runs is not None else []:
                (stores / "runs" / run.parent.name).mkdir(parents=True)
                shutil.copyfile(run, stores / "runs" / run.parent.name / "state.json")
            if allocations is not None and allocations.is_file():
                shutil.copyfile(allocations, stores / "allocations.json")
        return state

    return [*listed, _collect(directory, state, copy_stores)]


# ================================================
# Spans and the dossier's context
# ================================================


def spans(directory: Path, files: list[Path], origin: str) -> list[DossierSource]:
    """List span files, copying in those that live outside the dossier, each under a name of its own.

    A file that is not there is listed as unavailable rather than passed over.
    """
    return [_span(directory, path, origin) for path in files]


def _span(directory: Path, path: Path, origin: str) -> DossierSource:
    inside = path.resolve().is_relative_to(directory.resolve())
    relative = (
        path.resolve().relative_to(directory.resolve()) if inside else Path(TELEMETRY, _free_name(directory, path))
    )
    source = DossierSource(kind="spans", path=relative.as_posix(), origin=origin, name=path.stem)
    if not path.is_file():
        return _list(directory, source.model_copy(update={"status": "unavailable", "problem": f"no file {path}"}))

    def gather() -> DossierSource:
        if not inside:
            (directory / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, directory / relative)
        return source

    return _collect(directory, source, gather)


def _free_name(directory: Path, path: Path) -> str:
    """The name ``path`` gets among the dossier's span files: its own, numbered while another file holds it."""
    name, number = path.name, 1
    while (directory / TELEMETRY / name).exists() and not filecmp.cmp(
        directory / TELEMETRY / name, path, shallow=False
    ):
        name, number = f"{path.stem}-{number}{path.suffix}", number + 1
    return name


def finish(directory: Path, outcome: str | None = None) -> None:
    dossier = read_dossier(directory)
    context = dossier.context.model_copy(update={"outcome": outcome, "finished": time.time()})
    write_dossier(directory, dossier.model_copy(update={"context": context}))
