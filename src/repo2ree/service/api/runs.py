from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, HTTPException, Query

from repo2ree.service.api.build_runtime import (
    CreateBuildRuntimeRunPayload,
    create_build_run_state,
)
from repo2ree.service.api.run_management import (
    _append_run_log,
    _get_run_state,
    _list_run_states,
    _mark_cancel_requested,
    _paginate,
    _run_summary,
)


runs_router = APIRouter()


@runs_router.get("/api/v1/workspaces/{workspace_id}/runs")
def list_workspace_runs(
    workspace_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
):
    runs = _list_run_states(workspace_id)
    runs.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    page, next_cursor, has_more = _paginate(runs, cursor=cursor, limit=limit)
    items = [
        {
            key: run[key]
            for key in (
                "runId",
                "workspaceId",
                "operation",
                "status",
                "createdAt",
                "startedAt",
                "finishedAt",
                "outputs",
            )
        }
        for run in page
    ]
    return {"items": items, "nextCursor": next_cursor, "hasMore": has_more}


@runs_router.get("/api/v1/workspaces/{workspace_id}/runs/{run_id}")
def get_workspace_run(workspace_id: str, run_id: str):
    run_state = _get_run_state(workspace_id, run_id)
    return _run_summary(run_state)


@runs_router.get("/api/v1/workspaces/{workspace_id}/runs/{run_id}/logs")
def get_workspace_run_logs(
    workspace_id: str,
    run_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
):
    run_state = _get_run_state(workspace_id, run_id)
    logs = run_state.get("logs", [])
    page, next_cursor, has_more = _paginate(logs, cursor=cursor, limit=limit)
    return {
        "entries": page,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "runStatus": run_state["status"],
    }


@runs_router.post("/api/v1/workspaces/{workspace_id}/runs/{run_id}:retry")
def retry_workspace_run(workspace_id: str, run_id: str):
    from repo2ree.service.api.activation_test import (
        CreateActivationTestRunPayload,
        create_activation_run_state,
    )
    from repo2ree.service.api.evaluate import (
        CreateEvaluateRunPayload,
        create_evaluate_run_state,
    )
    from repo2ree.service.api.generate_sbom import (
        CreateGenerateSbomRunPayload,
        create_generate_sbom_run_state,
    )

    run_state = _get_run_state(workspace_id, run_id)
    request_payload = run_state.get("request", {})
    operation = run_state["operation"]
    if operation == "build":
        payload = CreateBuildRuntimeRunPayload(
            build_runtime_script_path=request_payload.get(
                "build_runtime_script_path", ""
            ),
            produced_runtime_path=request_payload.get("produced_runtime_path", ""),
        )
        return _run_summary(create_build_run_state(workspace_id, payload))
    if operation == "sbom":
        payload = CreateGenerateSbomRunPayload(
            produced_runtime_path=request_payload.get("produced_runtime_path", "")
        )
        return _run_summary(create_generate_sbom_run_state(workspace_id, payload))
    if operation == "activation":
        payload = CreateActivationTestRunPayload(
            activation_script_path=request_payload.get("activation_script_path", "")
        )
        return _run_summary(create_activation_run_state(workspace_id, payload))
    if operation == "evaluate":
        payload = CreateEvaluateRunPayload(
            strict=bool(request_payload.get("strict", False)),
            swhid_check=bool(request_payload.get("swhid_check", True)),
        )
        return _run_summary(create_evaluate_run_state(workspace_id, payload))
    raise HTTPException(
        status_code=400, detail=f"Unsupported operation for retry: {operation}"
    )


@runs_router.post("/api/v1/workspaces/{workspace_id}/runs/{run_id}:cancel")
def cancel_workspace_run(workspace_id: str, run_id: str):
    run_state = _get_run_state(workspace_id, run_id)
    current_status = run_state.get("status")
    if current_status in {"succeeded", "failed", "canceled"}:
        return {"status": current_status}

    _mark_cancel_requested(workspace_id, run_id)
    _append_run_log(
        workspace_id,
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
                ["sudo", docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            pass
    elif operation == "activation":
        container_name = f"repo2ree-activation-{run_id}"
        try:
            subprocess.run(
                ["sudo", docker_bin, "rm", "-f", container_name],
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    refreshed = _get_run_state(workspace_id, run_id)
    return {"status": refreshed["status"]}
