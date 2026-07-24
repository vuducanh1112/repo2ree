from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_core.reviews import ReviewSet
from repo2ree_protocol.command import ReviewAcquireSourceArgs, ReviewAcquireSourceCommand

reviews_router = APIRouter(tags=["reviews"])


class CreateSourceReviewPayload(CreateRunPayload):
    """Start a fresh isolated review attempt at source acquisition."""


@reviews_router.get(
    "/api/v1/rees/{ree_id}/reviews",
    operation_id="listReviews",
    response_model=ReviewSet,
    responses=ERROR_RESPONSES,
)
def list_reviews(ree_id: str) -> ReviewSet:
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return ReviewSet.model_validate(workbench_manager.get_reviews(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench review query failed: {exc}") from exc


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
