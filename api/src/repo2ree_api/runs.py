from __future__ import annotations

import logging
import shutil
import subprocess

from fastapi import APIRouter, Query

from repo2ree_api.api_utils import paginate
from repo2ree_api.run_management import (
    _append_run_log,
    _get_run_state,
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

    operation = run_state.get("operation")
    docker_bin = shutil.which("docker") or "docker"
    if operation == "build":
        container_name = f"repo2ree-build-{run_id}"
        try:
            subprocess.run(
                [docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            logger.warning("failed to kill build container %s", container_name, exc_info=True)
    elif operation == "activation":
        container_name = f"repo2ree-activation-{run_id}"
        try:
            subprocess.run(
                [docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            logger.warning("failed to kill activation container %s", container_name, exc_info=True)
    elif operation == "experiment":
        # Remove the main container AND any validator containers spawned for
        # custom-match evaluation (named repo2ree-experiment-validator-{run_id}-*).
        # Docker's --filter name= does a substring match, so the shared prefix
        # covers both container types.
        name_prefix = f"repo2ree-experiment-{run_id}"
        try:
            ps_result = subprocess.run(
                [docker_bin, "ps", "-aq", "--filter", f"name={name_prefix}"],
                capture_output=True,
                text=True,
            )
            ids = ps_result.stdout.split()
            if ids:
                subprocess.run(
                    [docker_bin, "rm", "-f", *ids],
                    capture_output=True,
                    text=True,
                )
        except Exception:
            logger.warning("failed to kill experiment containers for %s", run_id, exc_info=True)

    refreshed = _get_run_state(ree_id, run_id)
    return {"status": refreshed["status"]}
