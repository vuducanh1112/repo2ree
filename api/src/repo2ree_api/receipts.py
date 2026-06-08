from __future__ import annotations

from fastapi import APIRouter, HTTPException

from repo2ree_api.workbench.deps import workbench_manager


receipts_router = APIRouter()


@receipts_router.get("/api/v1/rees/{ree_id}/receipts")
def get_ree_receipts(ree_id: str):
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    receipts = workbench_manager.get_receipts(handle)
    return {"items": [r.model_dump(mode="json") for r in receipts]}
