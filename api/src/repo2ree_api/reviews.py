from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_core.reviews import ReviewRecord, ReviewSet
from repo2ree_protocol.command import (
    ReviewAcquireSourceArgs,
    ReviewAcquireSourceCommand,
    ReviewBuildRuntimeArgs,
    ReviewBuildRuntimeCommand,
)

reviews_router = APIRouter(tags=["reviews"])


class CreateSourceReviewPayload(CreateRunPayload):
    """Start a fresh isolated review attempt at source acquisition."""


class CreateBuildReviewPayload(CreateRunPayload):
    """Reproduce the runtime build inside an existing review attempt."""

    # Reviewers who mean to run activation next keep the rebuilt workspace; the
    # default reclaims it once the verdict is recorded (see ReviewBuildRuntimeArgs).
    prune_workspace: bool = True


def _reviews(ree_id: str) -> ReviewSet:
    """Every persisted attempt for an REE, or the workbench failure to report."""
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return ReviewSet.model_validate(workbench_manager.get_reviews(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench review query failed: {exc}") from exc


@reviews_router.get(
    "/api/v1/rees/{ree_id}/reviews",
    operation_id="listReviews",
    response_model=ReviewSet,
    responses=ERROR_RESPONSES,
)
def list_reviews(ree_id: str) -> ReviewSet:
    return _reviews(ree_id)


@reviews_router.get(
    "/api/v1/rees/{ree_id}/reviews/{review_id}",
    operation_id="getReview",
    response_model=ReviewRecord,
    responses=ERROR_RESPONSES,
)
def get_review(ree_id: str, review_id: str) -> ReviewRecord:
    for record in _reviews(ree_id).reviews:
        if record.review_id == review_id:
            return record
    raise HTTPException(status_code=404, detail="Review not found")


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/source:reproduce",
    operation_id="startSourceReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_source_review(ree_id: str, payload: CreateSourceReviewPayload) -> RunSummary:
    review_id = f"review-{uuid4().hex[:12]}"
    command = ReviewAcquireSourceCommand(args=ReviewAcquireSourceArgs(review_id=review_id))
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="source",
                command=command,
                run_id_prefix="review-source",
                request_payload={},
                canceled_message="Source review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/build:reproduce",
    operation_id="startBuildReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_build_review(ree_id: str, review_id: str, payload: CreateBuildReviewPayload) -> RunSummary:
    """Rebuild the runtime inside an attempt whose source was already reproduced.

    Addressed by review id rather than minting a new one: the build is only
    meaningful against the source *this* attempt fetched for itself, and the
    workbench rejects the command outright when that step has not settled.
    """
    command = ReviewBuildRuntimeCommand(
        args=ReviewBuildRuntimeArgs(review_id=review_id, prune_workspace=payload.prune_workspace)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="build",
                command=command,
                run_id_prefix="review-build",
                request_payload={"review_id": review_id},
                canceled_message="Build review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
