from __future__ import annotations

import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from repo2ree.service.storage.workspace_files import workspace_dir, workspace_exists


build_runtime_router = APIRouter()


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBuildRuntimeRunPayload(_StrictRequestModel):
    build_runtime_script_path: str
    produced_runtime_path: str
    idempotencyKey: str | None = None


RunOperation = Literal["build", "sbom", "activation"]


_RUN_STORE: dict[str, dict[str, dict[str, Any]]] = {}
_STORE_LOCK = RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_workspace(workspace_id: str) -> None:
    if not workspace_exists(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")


def _append_log(
    entries: list[dict[str, Any]],
    seq: int,
    stream: str,
    level: str,
    message: str,
) -> int:
    entries.append(
        {
            "seq": seq,
            "ts": _utc_now(),
            "stream": stream,
            "level": level,
            "message": message,
        }
    )
    return seq + 1


def _resolve_workspace_relative_path(workspace_id: str, relative_path: str) -> Path:
    root = workspace_dir(workspace_id).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid workspace path") from exc
    if candidate.name.startswith(".workspace") or candidate.name.startswith(".upload."):
        raise HTTPException(status_code=400, detail="Invalid workspace path")
    return candidate


def _require_non_empty_path(path_value: str, field_name: str) -> str:
    path = path_value.strip()
    if not path:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return path


def _docker_build_run(
    workspace_id: str,
    run_id: str,
    script_relative_path: str,
    runtime_relative_path: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    workspace_path = workspace_dir(workspace_id).resolve()
    script_abs_path = _resolve_workspace_relative_path(
        workspace_id, script_relative_path
    )
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Build script not found: {script_relative_path}"
        )

    script_in_container = Path("/workspace") / script_abs_path.relative_to(
        workspace_path
    )
    runtime_abs_path = _resolve_workspace_relative_path(
        workspace_id, runtime_relative_path
    )
    runtime_in_container = Path("/workspace") / runtime_abs_path.relative_to(
        workspace_path
    )

    entries: list[dict[str, Any]] = []
    seq = 1
    seq = _append_log(entries, seq, "system", "info", f"Starting build run {run_id}")
    seq = _append_log(
        entries, seq, "system", "info", "Starting container image docker:latest"
    )
    seq = _append_log(
        entries, seq, "system", "info", f"Build script: {script_relative_path}"
    )
    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        f"Expected runtime output: {runtime_relative_path}",
    )

    docker_bin = shutil.which("docker") or "docker"
    container_name = f"repo2ree-build-{run_id}"
    docker_create_cmd = [
        "sudo",
        docker_bin,
        "create",
        "--name",
        container_name,
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "docker:latest",
        "sleep",
        "infinity",
    ]
    docker_cp_cmd = [
        "sudo",
        docker_bin,
        "cp",
        f"{workspace_path}/.",
        f"{container_name}:/workspace",
    ]
    docker_start_cmd = ["sudo", docker_bin, "start", container_name]
    docker_exec_script_cmd = [
        "sudo",
        docker_bin,
        "exec",
        container_name,
        "sh",
        "-lc",
        (
            "set -e; "
            "cd /workspace; "
            f"echo '--- build_runtime_script ({shlex.quote(script_relative_path)}) ---'; "
            f"cat {shlex.quote(str(script_in_container))}; "
            "echo '--- end build_runtime_script ---'; "
            f"sh {shlex.quote(str(script_in_container))}; "
            f"sh -c ls {workspace_path}/*/"
            f"echo 'Expected runtime path: {shlex.quote(str(runtime_in_container))}'"
        ),
    ]
    docker_exec_check_cmd = [
        "sudo",
        docker_bin,
        "exec",
        container_name,
        "sh",
        "-lc",
        f"test -f {shlex.quote(str(runtime_in_container))}",
    ]
    docker_rm_cmd = ["sudo", docker_bin, "rm", "-f", container_name]

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_create_cmd),
    )
    create_result = subprocess.run(docker_create_cmd, capture_output=True, text=True)
    if create_result.returncode != 0:
        for line in create_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Build run failed (exit code {create_result.returncode})",
        )
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": create_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_cp_cmd),
    )
    cp_result = subprocess.run(docker_cp_cmd, capture_output=True, text=True)
    if cp_result.returncode != 0:
        for line in cp_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Build run failed (exit code {cp_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": cp_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_start_cmd),
    )
    start_result = subprocess.run(docker_start_cmd, capture_output=True, text=True)
    if start_result.returncode != 0:
        for line in start_result.stdout.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stdout", "info", line)
        for line in start_result.stderr.splitlines():
            if line.strip():
                seq = _append_log(entries, seq, "stderr", "warn", line)
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Container start failed (exit code {start_result.returncode})",
        )
        try:
            subprocess.run(docker_rm_cmd, capture_output=True, text=True)
        except Exception:
            pass
        outputs = {
            "buildRuntimeScriptPath": script_relative_path,
            "producedRuntimePath": runtime_relative_path,
            "dockerImage": "docker:latest",
            "containerExitCode": start_result.returncode,
        }
        return "failed", entries, outputs

    seq = _append_log(
        entries,
        seq,
        "system",
        "info",
        "$ " + " ".join(shlex.quote(token) for token in docker_exec_script_cmd),
    )
    exec_result = subprocess.run(docker_exec_script_cmd, capture_output=True, text=True)

    for line in exec_result.stdout.splitlines():
        if line.strip():
            seq = _append_log(entries, seq, "stdout", "info", line)
    for line in exec_result.stderr.splitlines():
        if line.strip():
            seq = _append_log(entries, seq, "stderr", "warn", line)

    if exec_result.returncode == 0:
        seq = _append_log(
            entries, seq, "system", "info", "Build script executed (exit code 0)"
        )
        seq = _append_log(
            entries,
            seq,
            "system",
            "info",
            f"Checking for produced runtime at {runtime_relative_path}",
        )
        check_result = subprocess.run(
            docker_exec_check_cmd, capture_output=True, text=True
        )

        if check_result.returncode == 0:
            docker_cp_back_cmd = [
                "sudo",
                docker_bin,
                "cp",
                f"{container_name}:{runtime_in_container}",
                str(runtime_abs_path),
            ]
            seq = _append_log(
                entries,
                seq,
                "system",
                "info",
                "$ " + " ".join(shlex.quote(token) for token in docker_cp_back_cmd),
            )
            cp_back_result = subprocess.run(
                docker_cp_back_cmd, capture_output=True, text=True
            )
            if cp_back_result.returncode == 0:
                seq = _append_log(
                    entries,
                    seq,
                    "system",
                    "info",
                    f"Successfully copied produced runtime to {runtime_relative_path}",
                )
            else:
                seq = _append_log(
                    entries,
                    seq,
                    "system",
                    "warn",
                    f"Produced runtime could not be copied from container at {runtime_relative_path}",
                )
                if cp_back_result.stderr.strip():
                    for line in cp_back_result.stderr.splitlines():
                        if line.strip():
                            seq = _append_log(entries, seq, "stderr", "warn", line)
        else:
            seq = _append_log(
                entries,
                seq,
                "system",
                "warn",
                f"Produced runtime not found in container at {runtime_relative_path}",
            )
    else:
        seq = _append_log(
            entries,
            seq,
            "system",
            "error",
            f"Build script failed (exit code {exec_result.returncode})",
        )

    try:
        subprocess.run(docker_rm_cmd, capture_output=True, text=True)
    except Exception:
        pass

    status = "succeeded" if exec_result.returncode == 0 else "failed"
    final_level = "info" if status == "succeeded" else "error"
    seq = _append_log(
        entries,
        seq,
        "system",
        final_level,
        f"Build run {status} (exit code {exec_result.returncode})",
    )

    outputs = {
        "buildRuntimeScriptPath": script_relative_path,
        "producedRuntimePath": runtime_relative_path,
        "dockerImage": "docker:latest",
        "containerExitCode": exec_result.returncode,
    }
    return status, entries, outputs


def _persist_run_state(
    workspace_id: str,
    run_id: str,
    operation: RunOperation,
    status: str,
    created_at: str,
    started_at: str,
    outputs: dict[str, Any],
    logs: list[dict[str, Any]],
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    finished_at = _utc_now()
    run_state = {
        "runId": run_id,
        "workspaceId": workspace_id,
        "operation": operation,
        "status": status,
        "createdAt": created_at,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "outputs": outputs,
        "logs": logs,
        "request": request_payload,
    }

    with _STORE_LOCK:
        _RUN_STORE.setdefault(workspace_id, {})[run_id] = run_state

    return run_state


def _run_summary(run_state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run_state[key]
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


def _create_build_run(
    workspace_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    _require_workspace(workspace_id)
    created_at = _utc_now()
    started_at = created_at
    run_id = f"build-{uuid4().hex}"
    script_path = _require_non_empty_path(
        payload.build_runtime_script_path,
        "build_runtime_script_path",
    )
    runtime_path = _require_non_empty_path(
        payload.produced_runtime_path,
        "produced_runtime_path",
    )
    status, logs, outputs = _docker_build_run(
        workspace_id=workspace_id,
        run_id=run_id,
        script_relative_path=script_path,
        runtime_relative_path=runtime_path,
    )
    request_payload = {
        "build_runtime_script_path": script_path,
        "produced_runtime_path": runtime_path,
    }
    return _persist_run_state(
        workspace_id=workspace_id,
        run_id=run_id,
        operation="build",
        status=status,
        created_at=created_at,
        started_at=started_at,
        outputs=outputs,
        logs=logs,
        request_payload=request_payload,
    )


def _get_run_state(workspace_id: str, run_id: str) -> dict[str, Any]:
    _require_workspace(workspace_id)
    with _STORE_LOCK:
        workspace_runs = _RUN_STORE.get(workspace_id, {})
        run_state = workspace_runs.get(run_id)
    if not run_state:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_state


def _paginate(
    items: list[dict[str, Any]], cursor: str | None, limit: int | None
) -> tuple[list[dict[str, Any]], str | None, bool]:
    start = 0
    if cursor:
        try:
            start = max(int(cursor), 0)
        except ValueError:
            start = 0
    end = len(items)
    if limit is not None and limit >= 0:
        end = min(start + limit, len(items))
    page = items[start:end]
    has_more = end < len(items)
    next_cursor = str(end) if has_more else None
    return page, next_cursor, has_more


@build_runtime_router.post("/api/v1/workspaces/{workspace_id}/build-runtime")
def create_workspace_build_runtime_run(
    workspace_id: str, payload: CreateBuildRuntimeRunPayload
):
    run_state = _create_build_run(workspace_id, payload)
    return _run_summary(run_state)


@build_runtime_router.get("/api/v1/workspaces/{workspace_id}/runs")
def list_workspace_runs(
    workspace_id: str,
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
):
    _require_workspace(workspace_id)
    with _STORE_LOCK:
        runs = list(_RUN_STORE.get(workspace_id, {}).values())
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


@build_runtime_router.get("/api/v1/workspaces/{workspace_id}/runs/{run_id}")
def get_workspace_run(workspace_id: str, run_id: str):
    run_state = _get_run_state(workspace_id, run_id)
    return _run_summary(run_state)


@build_runtime_router.get("/api/v1/workspaces/{workspace_id}/runs/{run_id}/logs")
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


@build_runtime_router.post("/api/v1/workspaces/{workspace_id}/runs/{run_id}:retry")
def retry_workspace_run(workspace_id: str, run_id: str):
    from repo2ree.service.api.activation_test import (
        CreateActivationTestRunPayload,
        create_activation_run_state,
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
        return create_workspace_build_runtime_run(workspace_id, payload)
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
    raise HTTPException(
        status_code=400, detail=f"Unsupported operation for retry: {operation}"
    )


@build_runtime_router.post("/api/v1/workspaces/{workspace_id}/runs/{run_id}:cancel")
def cancel_workspace_run(workspace_id: str, run_id: str):
    run_state = _get_run_state(workspace_id, run_id)
    run_state["status"] = "canceled"
    run_state["finishedAt"] = _utc_now()
    return {"status": run_state["status"]}
