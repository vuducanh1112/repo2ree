from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_commands import require_handle
from repo2ree_core.receipts import AuthorReceiptSet

receipts_router = APIRouter(tags=["receipts"])


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
