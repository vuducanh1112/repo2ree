"""Read captured operation attempts without exposing Git storage as raw files."""

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.persistence.operation_history import OperationHistory

history_router = APIRouter(tags=["history"])


@history_router.get(
    "/api/v1/rees/{ree_id}/history",
    operation_id="listOperationHistory",
    response_model=OperationHistory,
    responses=ERROR_RESPONSES,
)
def list_operation_history(ree_id: str) -> OperationHistory:
    handle = require_handle(ree_id)
    try:
        return OperationHistory.model_validate(workbench_manager.get_history(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench history query failed: {exc}") from exc
