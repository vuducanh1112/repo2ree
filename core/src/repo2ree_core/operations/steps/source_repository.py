from __future__ import annotations

from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.execution.launch import RECORD_PREFIX
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.source_repo import lay_source_repository, lfs_pointers
from repo2ree_core.workspace.attempt import lay_out
from repo2ree_ree.model import Ree
from repo2ree_ree.reserved_paths import RESERVED_SCRIPT_DIR
from repo2ree_ree.review import ReviewRecord


def _left_out(environment: object | None) -> tuple[str, ...]:
    ree_files = (f"/{RESERVED_SCRIPT_DIR}/", f"/{RECORD_PREFIX}*")
    return (*ree_files, f"/{environment}") if environment else ree_files


def lay_out_run(layout: ReeLayout, ree: Ree, run_id: str, *, environment: bool) -> Path:
    workspace = lay_out(layout, ree, run_id, environment=environment)
    receipt = ree.subject.receipts.acquire_source
    if receipt is None or receipt.resolved_revision is None or receipt.history is None:
        return workspace
    held = layout.source_history
    if not held.is_file() or digest_file(held) != receipt.history_digest:
        raise ReePreconditionError("the source history is not the one this REE acquired")
    lay_source_repository(
        workspace,
        held,
        revision=receipt.resolved_revision,
        history=receipt.history,
        left_out=_left_out(ree.subject.definition.experiment_environment.artifact_path),
        lfs=lfs_pointers(receipt.lfs_files),
    )
    return workspace


def lay_review_repository(review: ReviewLayout, record: ReviewRecord, workspace: Path) -> None:
    receipt = record.receipts.acquire_source
    if receipt is None or receipt.observed_revision is None or receipt.history is None:
        return
    if not review.source_history.is_file():
        raise ReePreconditionError("the source history this review acquired is missing")
    build = record.receipts.build_experiment_environment
    lay_source_repository(
        workspace,
        review.source_history,
        revision=receipt.observed_revision,
        history=receipt.history,
        left_out=_left_out(build.artifact_path if build else None),
        lfs=lfs_pointers(receipt.lfs_files),
    )
