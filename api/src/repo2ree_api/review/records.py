"""Reading review attempts back: every attempt for an REE, or one by id."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.evidence.review.models import ReviewRecord, ReviewSet

review_records_router = APIRouter(tags=["reviews"])


def reviews_for(ree_id: str) -> ReviewSet:
    """Every persisted attempt for an REE, or the workbench failure to report."""
    handle = require_handle(ree_id)
    try:
        return ReviewSet.model_validate(workbench_manager.get_reviews(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench review query failed: {exc}") from exc


@review_records_router.get(
    "/api/v1/rees/{ree_id}/reviews",
    operation_id="listReviews",
    response_model=ReviewSet,
    responses=ERROR_RESPONSES,
)
def list_reviews(ree_id: str) -> ReviewSet:
    return reviews_for(ree_id)


@review_records_router.get(
    "/api/v1/rees/{ree_id}/reviews/{review_id}",
    operation_id="getReview",
    response_model=ReviewRecord,
    responses=ERROR_RESPONSES,
)
def get_review(ree_id: str, review_id: str) -> ReviewRecord:
    for record in reviews_for(ree_id).reviews:
        if record.review_id == review_id:
            return record
    raise HTTPException(status_code=404, detail="Review not found")
