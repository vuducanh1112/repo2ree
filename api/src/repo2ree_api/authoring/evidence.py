"""What the authoring steps left behind, read back."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.domain.ree.model import Ree, ReeReceipts

receipts_router = APIRouter(tags=["receipts"])


@receipts_router.get(
    "/api/v1/rees/{ree_id}/receipts/author",
    operation_id="listAuthorReceipts",
    response_model=ReeReceipts,
    responses=ERROR_RESPONSES,
)
def list_author_receipts(ree_id: str) -> ReeReceipts:
    """Successful receipts carried by the portable aggregate."""
    handle = require_handle(ree_id)
    try:
        document = workbench_manager.get_ree_state(handle)
        return Ree.model_validate(document["ree"]).subject.receipts
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench receipt query failed: {exc}") from exc
