from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import workbench_manager
from repo2ree_core.reproducibility_scorecard import ReproducibilityScoreCard

# ================================================
# Router
# ================================================


scorecard_router = APIRouter(tags=["rees"])


# ================================================
# Route Handlers
# ================================================


@scorecard_router.get(
    "/api/v1/rees/{ree_id}/scorecard",
    operation_id="getScorecard",
    response_model=ReproducibilityScoreCard,
    responses=ERROR_RESPONSES,
)
def get_ree_scorecard(ree_id: str):
    """The reproducibility scorecard, computed inside the workbench from the
    REE's persisted record (intent + session + run receipts).
    """
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return workbench_manager.get_scorecard(handle)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench get-scorecard failed: {exc}") from exc
