"""What the authoring steps left behind, read back.

The scorecard grades the record; the receipts are the record's own account of
what ran. Both are computed inside the workbench from persisted state and are
pure reads — nothing here starts work. Two routers rather than one because they
answer to different tags in the published contract.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.evidence.consistency import AuthorReceiptSet
from repo2ree_core.evidence.scorecard import ReproducibilityScoreCard

scorecard_router = APIRouter(tags=["rees"])
receipts_router = APIRouter(tags=["receipts"])


@scorecard_router.get(
    "/api/v1/rees/{ree_id}/scorecard",
    operation_id="getScorecard",
    response_model=ReproducibilityScoreCard,
    responses=ERROR_RESPONSES,
)
def get_ree_scorecard(ree_id: str) -> ReproducibilityScoreCard:
    """The reproducibility scorecard, computed inside the workbench from the
    REE's persisted record (intent + state + run receipts).
    """
    handle = require_handle(ree_id)
    try:
        return ReproducibilityScoreCard.model_validate(workbench_manager.get_scorecard(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench get-scorecard failed: {exc}") from exc


@receipts_router.get(
    "/api/v1/rees/{ree_id}/receipts/author",
    operation_id="listAuthorReceipts",
    response_model=AuthorReceiptSet,
    responses=ERROR_RESPONSES,
)
def list_author_receipts(ree_id: str) -> AuthorReceiptSet:
    """Latest successful author receipt per operation, with live freshness."""
    handle = require_handle(ree_id)
    try:
        workspace = workbench_manager.get_workspace_state(handle)
        return AuthorReceiptSet.model_validate(workspace.get("author_receipts", {}))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench receipt query failed: {exc}") from exc
