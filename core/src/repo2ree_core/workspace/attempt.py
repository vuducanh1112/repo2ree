from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.persistence.layout import ARTIFACTS_DIRNAME, ReeLayout
from repo2ree_ree.model import Ree

_SUFFIX = ".workspace"


def attempt_workspace(layout: ReeLayout, run_id: str) -> Path:
    return layout.runs / f"{run_id}{_SUFFIX}"


def environment_file(layout: ReeLayout, declared: str) -> Path:
    return layout.kept_environment(declared)


def _clear(layout: ReeLayout) -> None:
    if layout.runs.is_dir():
        for left in layout.runs.glob(f"*{_SUFFIX}"):
            shutil.rmtree(left, ignore_errors=True)


def _source(layout: ReeLayout, ree: Ree, workspace: Path) -> None:
    receipt = ree.subject.receipts.acquire_source
    if receipt is None:
        return
    archive = layout.snapshot_archive
    if not archive.is_file():
        raise ReePreconditionError("the source snapshot this REE acquired is missing")
    if digest_file(archive) != receipt.snapshot_digest:
        raise ReePreconditionError("the source snapshot is not the one this REE acquired")
    with tarfile.open(archive, mode="r:gz") as tar:
        tar.extractall(workspace, filter="tar")


def _environment(layout: ReeLayout, ree: Ree, workspace: Path) -> None:
    declared = ree.subject.definition.experiment_environment.artifact_path
    build = ree.subject.receipts.build_experiment_environment
    if declared is None:
        return
    if build is None:
        raise ReePreconditionError("experiment environment has not been built")
    kept = environment_file(layout, str(declared))
    if not kept.is_file():
        raise ReePreconditionError(f"experiment environment artifact is missing: {declared}")
    if digest_file(kept) != build.produced_artifact_digest:
        raise ReePreconditionError("experiment environment artifact does not match the selected build receipt")
    target = workspace / str(declared)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kept, target)


def fresh(layout: ReeLayout, run_id: str) -> Path:
    _clear(layout)
    workspace = attempt_workspace(layout, run_id)
    workspace.mkdir(parents=True)
    return workspace


def overlay_onto(layout: ReeLayout, workspace: Path) -> None:
    if layout.overlay.is_dir():
        shutil.copytree(layout.overlay, workspace, symlinks=True, dirs_exist_ok=True)


def lay_out(layout: ReeLayout, ree: Ree, run_id: str, *, environment: bool) -> Path:
    workspace = fresh(layout, run_id)
    _source(layout, ree, workspace)
    overlay_onto(layout, workspace)
    if environment:
        _environment(layout, ree, workspace)
    return workspace


def environment_in_workspace(workspace: Path, declared: str) -> tuple[Path, ...]:
    parts = PurePosixPath(declared).parts
    if len(parts) == 2 and parts[0] == ARTIFACTS_DIRNAME:
        return (workspace / declared, workspace / parts[1])
    return (workspace / declared,)


def keep_environment(layout: ReeLayout, workspace: Path, declared: str) -> Path | None:
    produced = workspace / declared
    if not produced.is_file():
        return None
    kept = environment_file(layout, declared)
    kept.parent.mkdir(parents=True, exist_ok=True)
    produced.replace(kept)
    return kept


def show_environment(layout: ReeLayout, declared: str | None) -> None:
    if not declared:
        return
    kept = environment_file(layout, declared)
    view = layout.workspace / declared
    if not kept.is_file() or view.resolve() == kept.resolve():
        return
    view.parent.mkdir(parents=True, exist_ok=True)
    view.unlink(missing_ok=True)
    try:
        os.link(kept, view)
    except OSError:
        shutil.copy2(kept, view)


def discard(layout: ReeLayout, run_id: str) -> None:
    shutil.rmtree(attempt_workspace(layout, run_id), ignore_errors=True)
