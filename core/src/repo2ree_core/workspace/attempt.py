"""The workspace one attempt runs in: what the REE records, laid out fresh, and nothing else.

Every script a step runs, runs in a workspace of its own, laid out for that attempt from what the REE records: the
source from its snapshot archive, as its acquisition's digest names it; the overlay; and, for a step that uses it, the
experiment environment, as its build's digest names it. Nothing an earlier step left behind reaches a later one, and
nothing changed meanwhile in the REE's own ``workspace/`` or ``upstream/``, which are views for people, reaches any.
A step that needs what a build made beside its artifact has an artifact that does not hold all it needs: it fails
here, as it would for a reviewer given the sealed experiment environment.

A step's workspace stays until the next attempt lays out its own, for a failed one to be looked into.
"""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.model import Ree

# Where an attempt's workspace is, beside the run's log, by the run's id.
_SUFFIX = ".workspace"


def attempt_workspace(layout: ReeLayout, run_id: str) -> Path:
    return layout.runs / f"{run_id}{_SUFFIX}"


def environment_file(layout: ReeLayout, declared: str) -> Path:
    """Where the built experiment environment declared at ``declared`` is kept."""
    return layout.kept_environment(declared)


def _clear(layout: ReeLayout) -> None:
    """Remove the workspaces earlier attempts left, kept only until the next attempt."""
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


def lay_out(layout: ReeLayout, ree: Ree, run_id: str, *, environment: bool) -> Path:
    """A fresh workspace for the attempt ``run_id``: the source as acquired, the overlay over it, and, with
    ``environment``, the built experiment environment at its declared path. Raises ReePreconditionError when what the
    REE records is not there as it records it."""
    _clear(layout)
    workspace = attempt_workspace(layout, run_id)
    workspace.mkdir(parents=True)
    _source(layout, ree, workspace)
    if layout.overlay.is_dir():
        shutil.copytree(layout.overlay, workspace, symlinks=True, dirs_exist_ok=True)
    if environment:
        _environment(layout, ree, workspace)
    return workspace


def keep_environment(layout: ReeLayout, workspace: Path, declared: str) -> Path | None:
    """Move the experiment environment a build left in ``workspace`` at ``declared`` to where it is kept; None when
    the build left none."""
    produced = workspace / declared
    if not produced.is_file():
        return None
    kept = environment_file(layout, declared)
    kept.parent.mkdir(parents=True, exist_ok=True)
    produced.replace(kept)
    return kept


def discard(layout: ReeLayout, run_id: str) -> None:
    """Remove the workspace of an attempt that succeeded: nothing in it is the REE's."""
    shutil.rmtree(attempt_workspace(layout, run_id), ignore_errors=True)
