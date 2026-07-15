from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    CancelRunResponse,
    RunList,
    RunLogPage,
    RunObservation,
    RunSummary,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import (
    _append_run_log,
    _get_run_state,
    _list_runs,
    _mark_cancel_requested,
    _observe_run,
    _run_summary,
)
from repo2ree_api.run_registry import TERMINAL_STATUSES

logger = logging.getLogger(__name__)

# ================================================
# Router
# ================================================


runs_router = APIRouter(tags=["runs"])


# ================================================
# Route Handlers
# ================================================


@runs_router.get(
    "/api/v1/rees/{ree_id}/runs",
    operation_id="listRuns",
    response_model=RunList,
    responses=ERROR_RESPONSES,
)
def list_workspace_runs(ree_id: str):
    return {"runs": _list_runs(ree_id)}


@runs_router.get(
    "/api/v1/rees/{ree_id}/runs/{run_id}",
    operation_id="getRun",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def get_workspace_run(ree_id: str, run_id: str):
    run_state = _get_run_state(ree_id, run_id)
    return _run_summary(run_state)


@runs_router.get(
    "/api/v1/rees/{ree_id}/runs/{run_id}/logs",
    operation_id="listRunLogs",
    response_model=RunLogPage,
    responses=ERROR_RESPONSES,
)
def get_workspace_run_logs(
    ree_id: str,
    run_id: str,
    cursor: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    run_state = _get_run_state(ree_id, run_id)
    after_seq = cursor or 0
    remaining = [entry for entry in run_state.get("logs", []) if int(entry["seq"]) > after_seq]
    page = remaining[:limit]
    next_cursor = str(page[-1]["seq"]) if page else (str(after_seq) if cursor is not None else None)
    return {
        "entries": page,
        "nextCursor": next_cursor,
        "hasMore": len(remaining) > len(page),
        "runStatus": run_state["status"],
    }


@runs_router.get(
    "/api/v1/rees/{ree_id}/runs/{run_id}/observe",
    operation_id="observeRun",
    response_model=RunObservation,
    responses=ERROR_RESPONSES,
)
def observe_workspace_run(
    ree_id: str,
    run_id: str,
    cursor: Annotated[int | None, Query(ge=0)] = None,
    wait_seconds: Annotated[float, Query(alias="waitSeconds", ge=0, le=30)] = 25,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    run, entries, next_cursor, changed = _observe_run(
        ree_id,
        run_id,
        after_seq=cursor or 0,
        wait_seconds=wait_seconds,
        limit=limit,
    )
    return {"run": run, "entries": entries, "nextCursor": next_cursor, "changed": changed}


@runs_router.post(
    "/api/v1/rees/{ree_id}/runs/{run_id}:cancel",
    operation_id="cancelRun",
    response_model=CancelRunResponse,
    responses=ERROR_RESPONSES,
)
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
