"""Whether an REE's files and history are as its last attempt left them.

Every attempt ends by stamping the REE: each file its history holds, the workspace its scripts run in, and the commit
each ref of its history names; each review of it is stamped the same, in its own history. Before the next attempt
the REE is checked against those stamps, so a file changed, added or removed in between, or a history committed to,
reset or rewritten, by an editor, a disk, git or anything else that is not ree, is drift: it is found, never
absorbed. The stamps are a cache beside the history, not evidence; what an attempt found is in its record. They
guard against mistakes, not against someone rewriting them too.

A stamp is a file's size, modification time and mode, with the digest of its content: a file whose size or time
differs is read, and has drifted only if its content or mode differs too.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import HistoryCaptureError, selected_files
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.history import DriftedFile, ReePart
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.layout import OVERLAY, WORKSPACE
from repo2ree_ree.reserved_paths import WORKSPACE_CONTROL_PREFIXES, is_overlay_path

# Where a ref is named among an REE's files: in its version storage, which no file view shows.
HISTORY = ".git"


class Stamp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    size: int
    mtime_ns: int
    mode: int
    digest: str


class Stamps(BaseModel):
    """Each file of the REE, by its path from the REE, and each ref of its history with the commit it names, as the
    last attempt left them."""

    model_config = ConfigDict(extra="forbid")

    files: dict[str, Stamp]
    refs: dict[str, str]


def _stamps_path(layout: ReeLayout) -> Path:
    return layout.git_dir / "repo2ree" / "stamps.json"


def _part(relative: str) -> ReePart:
    parts = PurePosixPath(relative).parts
    top = parts[0]
    if top == HISTORY:
        return "history"
    return "overlay" if top == OVERLAY else "workspace" if top == WORKSPACE else "records"


def _ree_files(layout: ReeLayout) -> dict[str, os.stat_result]:
    """Every file the stamps cover, by its path from the REE, with what ``lstat`` says of it."""
    found = {path.relative_to(layout.root).as_posix(): path.lstat() for path in selected_files(layout)}
    if layout.workspace.is_dir():
        for directory, _dirs, files in layout.workspace.walk():
            for name in files:
                if name.startswith(WORKSPACE_CONTROL_PREFIXES):
                    continue
                path = directory / name
                info = path.lstat()
                if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                    found[path.relative_to(layout.root).as_posix()] = info
    return found


def _refs(layout: ReeLayout) -> dict[str, str]:
    """Each ref of the REE's history, with the commit it names."""
    if not layout.git_dir.is_dir():
        return {}
    executable = find_tool("git")
    if executable is None:
        raise HistoryCaptureError("git is not available to read the REE's history")
    listed = subprocess.run(
        [executable, "--git-dir", str(layout.git_dir), "for-each-ref", "--format=%(refname) %(objectname)"],
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode:
        raise HistoryCaptureError(f"cannot read the REE's history: {listed.stderr.strip()}")
    return dict(line.split(" ", 1) for line in listed.stdout.splitlines() if " " in line)


def _digest(path: Path, info: os.stat_result) -> str:
    if stat.S_ISLNK(info.st_mode):
        return digest_bytes(os.fsencode(path.readlink()))
    return digest_file(path)


def _same(stamp: Stamp, info: os.stat_result) -> bool:
    return stamp.size == info.st_size and stamp.mtime_ns == info.st_mtime_ns and stamp.mode == info.st_mode


def _unchanged(path: Path, stamp: Stamp, info: os.stat_result) -> bool:
    return _same(stamp, info) or (stamp.mode == info.st_mode and _digest(path, info) == stamp.digest)


def read_stamps(layout: ReeLayout) -> Stamps | None:
    """The stamps the last attempt left in this REE or review; None for one no attempt stamped yet."""
    path = _stamps_path(layout)
    if not path.is_file():
        return None
    return Stamps.model_validate_json(path.read_text(encoding="utf-8"))


def stamp_ree(layout: ReeLayout) -> None:
    """Stamp the REE or review at ``layout`` as it is now; only a file whose size or time changed is read again."""
    previous = read_stamps(layout)
    known = previous.files if previous else {}
    stamps: dict[str, Stamp] = {}
    for relative, info in _ree_files(layout).items():
        stamp = known.get(relative)
        if stamp is None or not _same(stamp, info):
            stamp = Stamp(
                size=info.st_size,
                mtime_ns=info.st_mtime_ns,
                mode=info.st_mode,
                digest=_digest(layout.root / relative, info),
            )
        stamps[relative] = stamp
    write_json_atomic(_stamps_path(layout), Stamps(files=stamps, refs=_refs(layout)).model_dump(mode="json"))


def stamp_history(layout: ReeLayout) -> None:
    """Stamp the refs of the history at ``layout`` as they are now, and leave its files' stamps as they were: what an
    attempt refused for drift commits moves its history, never its files."""
    previous = read_stamps(layout)
    if previous is not None:
        restamped = previous.model_copy(update={"refs": _refs(layout)})
        write_json_atomic(_stamps_path(layout), restamped.model_dump(mode="json"))


def reviews_of(layout: ReeLayout) -> list[ReeLayout]:
    """Every review of the REE that has a history of its own."""
    if not layout.reviews.is_dir():
        return []
    return [layout.review(path.name) for path in sorted(layout.reviews.iterdir()) if (path / HISTORY).is_dir()]


def stamp_rees(layout: ReeLayout, scope: ReeLayout) -> None:
    """Stamp the REE, the review an attempt ran in, and each review no attempt stamped yet, such as one a bundle
    brought: what the attempt left. A review that drifted meanwhile keeps its stamps, so it stays found."""
    stamp_ree(layout)
    for review in reviews_of(layout):
        if review.root == scope.root or read_stamps(review) is None:
            stamp_ree(review)


def _drift_in(scope: ReeLayout, stamps: Stamps, ree: Path) -> list[DriftedFile]:
    within = scope.root.relative_to(ree).as_posix()
    prefix = "" if within == "." else f"{within}/"
    current = _ree_files(scope)
    drifted = []
    for relative in sorted(set(stamps.files) | set(current)):
        stamp, info = stamps.files.get(relative), current.get(relative)
        if stamp is not None and info is not None and _unchanged(scope.root / relative, stamp, info):
            continue
        drifted.append(DriftedFile(path=f"{prefix}{relative}", part=_part(relative)))
    refs = _refs(scope)
    moved = [ref for ref in sorted(set(stamps.refs) | set(refs)) if stamps.refs.get(ref) != refs.get(ref)]
    return [*drifted, *(DriftedFile(path=f"{prefix}{HISTORY}/{ref}", part="history") for ref in moved)]


def find_drift(layout: ReeLayout) -> list[DriftedFile] | None:
    """Everything of the REE and its reviews not as the last attempt left it, by its path from the REE; None for an
    REE no attempt stamped yet. A review no attempt stamped yet has none. Nothing is written."""
    stamps = read_stamps(layout)
    if stamps is None:
        return None
    drifted = _drift_in(layout, stamps, layout.root)
    for review in reviews_of(layout):
        if (kept := read_stamps(review)) is not None:
            drifted += _drift_in(review, kept, layout.root)
    return drifted


def history_hints(layout: ReeLayout, drift: list[DriftedFile]) -> list[str]:
    """For each ref that moved, the git command that puts it back where ree left it."""
    hints = []
    for item in drift:
        if item.part != "history":
            continue
        within, _, ref = item.path.partition(f"{HISTORY}/")
        review = PurePosixPath(within).name if within else None
        stamps = read_stamps(layout.review(review) if review else layout)
        left = stamps.refs.get(ref) if stamps else None
        where = f" -C {within.rstrip('/')}" if within else ""
        hints.append(f"git{where} update-ref {ref} {left}" if left else f"git{where} update-ref -d {ref}")
    return hints


def recordable_edits(layout: ReeLayout, drift: list[DriftedFile]) -> list[str]:
    """The scripts edited in ``overlay/`` that attempts can record as written, by their path from the overlay.

    Only when every drifted file is such a script: one of the REE's scripts, edited, never added or removed, whose
    workspace copy is as it was. Any other drift is recorded by nothing, so then none of them is.
    """
    stamps = read_stamps(layout)
    drifted = {item.path for item in drift}
    edits = []
    for item in drift:
        relative = PurePosixPath(item.path)
        script = PurePosixPath(*relative.parts[1:]).as_posix()
        recordable = (
            item.part == "overlay"
            and is_overlay_path(script)
            and PurePosixPath(WORKSPACE, script).as_posix() not in drifted
            and (layout.root / relative).is_file()
            and stamps is not None
            and item.path in stamps.files
        )
        if not recordable:
            return []
        edits.append(script)
    return edits


def lay_out_scripts(layout: ReeLayout) -> None:
    """Make each script in the workspace what the REE records once its files were put back: the overlay's, else the
    source's, else none. A restore puts back only what the history holds, and a script's workspace copy is not."""
    scripts = {
        path.relative_to(base).as_posix()
        for base in (layout.overlay, layout.workspace)
        if base.is_dir()
        for path in base.rglob("*")
        if path.is_file() and is_overlay_path(path.relative_to(base).as_posix())
    }
    for script in sorted(scripts):
        copy = layout.workspace / script
        recorded = next(
            (base / script for base in (layout.overlay, layout.upstream) if (base / script).is_file()), None
        )
        if recorded is None:
            copy.unlink(missing_ok=True)
        elif not copy.is_file() or copy.read_bytes() != recorded.read_bytes():
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(recorded.read_bytes())
