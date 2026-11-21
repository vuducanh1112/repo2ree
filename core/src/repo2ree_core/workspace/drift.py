"""Observe mutations in a materialized workspace against its durable inputs."""

from __future__ import annotations

import filecmp
import json
import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath

from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.workspace.materialization import stat_table
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.primitives import WorkspacePath
from repo2ree_ree.receipt import WorkspaceDrift
from repo2ree_ree.reserved_paths import WORKSPACE_CONTROL_PREFIXES

_DRIFT_PATHS_CAP = 20


def _is_control_name(relative: str) -> bool:
    return PurePosixPath(relative).name.startswith(WORKSPACE_CONTROL_PREFIXES)


def check_workspace_drift(layout: ReeLayout, *, excluded_paths: set[str]) -> WorkspaceDrift:
    """Compare the mutable workspace with current ``upstream + overlay``."""
    if not layout.materialize_marker.is_file():
        return WorkspaceDrift(status="unknown")
    try:
        marker = json.loads(layout.materialize_marker.read_text(encoding="utf-8"))
        recorded: dict[str, list[int]] = dict(marker.get("files") or {})
    except Exception:  # noqa: BLE001 — an unreadable marker has the explicit unknown verdict
        return WorkspaceDrift(status="unknown")

    current = stat_table(layout.workspace)
    drifted: list[str] = []

    def expected_file(relative: str) -> Path | None:
        for base in (layout.overlay, layout.upstream):
            candidate = base / relative
            if candidate.is_file():
                return candidate
        return None

    for relative in sorted(set(recorded) | set(current)):
        if relative in excluded_paths or _is_control_name(relative) or recorded.get(relative) == current.get(relative):
            continue
        expected = expected_file(relative)
        actual = layout.workspace / relative
        if not actual.is_file():
            if expected is not None:
                drifted.append(relative)
            continue
        if expected is None or digest_file(actual) != digest_file(expected):
            drifted.append(relative)

    if not drifted:
        return WorkspaceDrift(status="clean")
    return WorkspaceDrift(
        status="modified",
        changed_paths=tuple(WorkspacePath(path) for path in drifted[:_DRIFT_PATHS_CAP]),
        changed_path_count=len(drifted),
    )


# ---- What of the workspace is derived, and whether it is as it should be -----------------------------------------
#
# The workspace holds three kinds of file. Derived ones are laid out from the REE's inputs: the overlay's copy of a
# path, else the source's. Generated ones are what the REE declares its steps make, the experiment environment and
# each experiment's outputs; receipts vouch for those, through their digests. Anything else is a step's by-product or
# a file someone put there, which nothing records, so nothing can have drifted in it.


# A file's input: the source's file on disk, or the overlay's as a history holds it, by its git blob and mode.
type Input = Path | tuple[str, str]
# Git's blob id of each of a list of files, as git hashes them.
type BlobHasher = Callable[[list[Path]], list[str]]


def _inputs(layout: ReeLayout, overlay: Mapping[str, tuple[str, str]] | None) -> dict[str, Input]:
    """Each derived path, from the workspace, with what it is laid out from: the overlay's, else the source's. The
    overlay is ``overlay``, as a history holds it (path from the overlay to mode and blob), or, without it, on disk."""
    found: dict[str, Input] = {}
    bases = (layout.upstream,) if overlay is not None else (layout.upstream, layout.overlay)
    for base in bases:
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_symlink() or path.is_file():
                    found[path.relative_to(base).as_posix()] = path
    if overlay is not None:
        found.update(overlay)
    return found


def _generated(layout: ReeLayout) -> tuple[str, ...]:
    """The paths the REE declares its steps make, from the workspace."""
    if not layout.manifest.is_file():
        return ()
    definition = ReeDirectory(layout).read_ree().subject.definition
    paths = [str(path) for experiment in definition.experiments for path in experiment.output_paths]
    if definition.experiment_environment.artifact_path is not None:
        paths.append(str(definition.experiment_environment.artifact_path))
    return tuple(PurePosixPath(path).as_posix().strip("/") for path in paths)


def _within(relative: str, roots: tuple[str, ...]) -> bool:
    return any(relative == root or relative.startswith(f"{root}/") for root in roots)


def _digest_of(path: Path) -> str:
    if path.is_symlink():
        return digest_bytes(os.fsencode(path.readlink()))
    return digest_file(path)


def _git_mode(path: Path) -> str:
    if path.is_symlink():
        return "120000"
    return "100755" if path.lstat().st_mode & 0o111 else "100644"


def _materialized(layout: ReeLayout) -> dict[str, list[int]]:
    """The size and time of each file as materializing left it: a cache only, empty when it was lost."""
    try:
        marker = json.loads(layout.materialize_marker.read_text(encoding="utf-8"))
        return dict(marker.get("files") or {})
    except (OSError, ValueError, AttributeError):
        return {}


def _deviations(
    layout: ReeLayout,
    expected: Mapping[str, str | None],
    overlay: Mapping[str, tuple[str, str]] | None = None,
    hash_blobs: BlobHasher | None = None,
) -> dict[str, str | None]:
    """Each derived file neither laid out from its input nor as a step left it (``expected``: a digest, or None for a
    file a step removed), with what it is now: its digest, or None when it is gone."""
    if not layout.workspace.is_dir():
        return {}
    generated = _generated(layout)
    cached = _materialized(layout)
    found: dict[str, str | None] = {}
    by_blob: list[tuple[str, Path, str]] = []
    for relative, source in sorted(_inputs(layout, overlay).items()):
        if _is_control_name(relative) or _within(relative, generated):
            continue
        actual = layout.workspace / relative
        present = actual.is_symlink() or actual.exists()
        if relative in expected:
            now = _digest_of(actual) if present else None
            if now != expected[relative]:
                found[relative] = now
            continue
        if not present or (actual.is_dir() and not actual.is_symlink()):
            found[relative] = None
            continue
        info = actual.lstat()
        unchanged = cached.get(relative) == [info.st_size, info.st_mtime_ns]
        if isinstance(source, tuple):
            mode, blob = source
            if _git_mode(actual) != mode:
                found[relative] = _digest_of(actual)
            elif not unchanged:
                by_blob.append((relative, actual, blob))
        elif _git_mode(actual) != _git_mode(source) or (
            not unchanged
            and (
                source.readlink() != actual.readlink()
                if source.is_symlink()
                else not filecmp.cmp(source, actual, shallow=False)
            )
        ):
            found[relative] = _digest_of(actual)
    if by_blob:
        if hash_blobs is None:
            raise ValueError("a file laid out from a history's overlay needs git to compare it")
        hashed = hash_blobs([actual for _, actual, _ in by_blob])
        for (relative, actual, blob), now in zip(by_blob, hashed, strict=True):
            if now != blob:
                found[relative] = _digest_of(actual)
    return found


def derived_changes(layout: ReeLayout) -> dict[str, str | None]:
    """Each derived file of the workspace not as materializing lays it out from the inputs on disk, with its digest,
    or None when it is gone: what an attempt that ends leaves in its record, for the next to hold the workspace to."""
    return _deviations(layout, {})


def derived_drift(
    layout: ReeLayout,
    left: Mapping[str, str | None],
    overlay: Mapping[str, tuple[str, str]],
    hash_blobs: BlobHasher,
) -> list[str]:
    """Each derived file of the workspace, by its path from the workspace, not as the last attempt left it: laid out
    from its input, the overlay as the history holds it (``overlay``), or as ``left``, that attempt's record of what
    it changed, names it."""
    return sorted(_deviations(layout, left, overlay, hash_blobs))


def lay_out_again(layout: ReeLayout, paths: list[str]) -> None:
    """Lay out each derived file of ``paths`` from its input on disk again, and nothing else of the workspace."""
    inputs = _inputs(layout, None)
    for relative in paths:
        source, target = inputs.get(relative), layout.workspace / relative
        if target.is_symlink() or target.is_file():
            target.unlink()
        if not isinstance(source, Path):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(source.readlink())
        else:
            shutil.copy2(source, target)
