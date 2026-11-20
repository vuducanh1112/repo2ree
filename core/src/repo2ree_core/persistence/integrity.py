"""Whether an REE's files are as its last attempt left them.

Every attempt ends by stamping each file of the REE: those its history holds, and the workspace its scripts run in.
Before the next attempt the files are checked against those stamps, so a file changed, added or removed in between,
by an editor, a disk or anything else that is not ree, is drift: it is found, never absorbed. The stamps are a
cache beside the history, not evidence; what an attempt found is in its record.

A stamp is a file's size, modification time and mode, with the digest of its content: a file whose size or time
differs is read, and has drifted only if its content or mode differs too.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import selected_files
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.history import DriftedFile, ReePart
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.layout import OVERLAY, WORKSPACE
from repo2ree_ree.reserved_paths import WORKSPACE_CONTROL_PREFIXES, is_overlay_path


class Stamp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    size: int
    mtime_ns: int
    mode: int
    digest: str


class Stamps(BaseModel):
    """Each file of the REE, by its path from the REE, as the last attempt left it."""

    model_config = ConfigDict(extra="forbid")

    files: dict[str, Stamp]


def _stamps_path(layout: ReeLayout) -> Path:
    return layout.git_dir / "repo2ree" / "stamps.json"


def _part(relative: str) -> ReePart:
    top = PurePosixPath(relative).parts[0]
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


def _digest(path: Path, info: os.stat_result) -> str:
    if stat.S_ISLNK(info.st_mode):
        return digest_bytes(os.fsencode(path.readlink()))
    return digest_file(path)


def _same(stamp: Stamp, info: os.stat_result) -> bool:
    return stamp.size == info.st_size and stamp.mtime_ns == info.st_mtime_ns and stamp.mode == info.st_mode


def _unchanged(path: Path, stamp: Stamp, info: os.stat_result) -> bool:
    return _same(stamp, info) or (stamp.mode == info.st_mode and _digest(path, info) == stamp.digest)


def read_stamps(layout: ReeLayout) -> Stamps | None:
    """The stamps the last attempt left; None for an REE no attempt stamped yet."""
    path = _stamps_path(layout)
    if not path.is_file():
        return None
    return Stamps.model_validate_json(path.read_text(encoding="utf-8"))


def stamp_ree(layout: ReeLayout) -> None:
    """Stamp every file of the REE as it is now; only a file whose size or time changed is read again."""
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
    write_json_atomic(_stamps_path(layout), Stamps(files=stamps).model_dump(mode="json"))


def find_drift(layout: ReeLayout) -> list[DriftedFile] | None:
    """Every file not as the last attempt left it; None for an REE no attempt stamped yet. Nothing is written."""
    stamps = read_stamps(layout)
    if stamps is None:
        return None
    current = _ree_files(layout)
    drifted = []
    for relative in sorted(set(stamps.files) | set(current)):
        stamp, info = stamps.files.get(relative), current.get(relative)
        if stamp is not None and info is not None and _unchanged(layout.root / relative, stamp, info):
            continue
        drifted.append(DriftedFile(path=relative, part=_part(relative)))
    return drifted


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
