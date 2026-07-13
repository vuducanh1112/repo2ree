from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from repo2ree_api.api_utils import paginate
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import (
    _append_run_log,
    _get_run_state,
    _list_runs,
    _mark_cancel_requested,
    _run_summary,
)
from repo2ree_api.run_registry import TERMINAL_STATUSES

logger = logging.getLogger(__name__)

# ================================================
# Router
# ================================================


runs_router = APIRouter()


# ================================================
# Route Handlers
# ================================================


@runs_router.get("/api/v1/rees/{ree_id}/runs")
def list_workspace_runs(ree_id: str):
    return {"runs": _list_runs(ree_id)}


@runs_router.get("/api/v1/rees/{ree_id}/runs/{run_id}")
def get_workspace_run(ree_id: str, run_id: str):
    run_state = _get_run_state(ree_id, run_id)
    return _run_summary(run_state)


@runs_router.get("/api/v1/rees/{ree_id}/runs/{run_id}/logs")
def get_workspace_run_logs(
    ree_id: str,
    run_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
):
    run_state = _get_run_state(ree_id, run_id)
    logs = run_state.get("logs", [])
    page, next_cursor, has_more = paginate(logs, cursor=cursor, limit=limit)
    return {
        "entries": page,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "runStatus": run_state["status"],
    }


@runs_router.post("/api/v1/rees/{ree_id}/runs/{run_id}:cancel")
def cancel_workspace_run(ree_id: str, run_id: str):
    run_state = _get_run_state(ree_id, run_id)
    current_status = run_state.get("status")
    if current_status in TERMINAL_STATUSES:
        return {"status": current_status}

    _mark_cancel_requested(ree_id, run_id)
    _append_run_log(
        ree_id,
        run_id,
        "system",
        "warn",
        "Cancel requested by user",
    )

    handle = workbench_manager.lookup(ree_id)
    if handle is not None:
        try:
            workbench_manager.cancel_run(handle, run_id)
        except Exception:
            logger.warning("failed to signal cancellation for %s", run_id, exc_info=True)
            _append_run_log(
                ree_id,
                run_id,
                "system",
                "warn",
                "Cancellation signal could not reach the workbench",
            )
    else:
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "warn",
            "Cancellation signal deferred: workbench is not currently reachable",
        )

    refreshed = _get_run_state(ree_id, run_id)
    return {"status": refreshed["status"]}
