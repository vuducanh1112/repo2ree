from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.container.run_script import (
    ContainerScriptRun,
    run_script_in_container,
)
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _start_background_run,
    _run_summary,
)
from repo2ree_api.storage.workspace_files import workspace_dir


build_runtime_router = APIRouter()


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBuildRuntimeRunPayload(_StrictRequestModel):
    build_runtime_script_path: str
    idempotencyKey: str | None = None


def _resolve_workspace_relative_path(ree_id: str, relative_path: str) -> Path:
    root = workspace_dir(ree_id).resolve()
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
    ree_id: str,
    run_id: str,
    script_relative_path: str,
) -> tuple[str, dict[str, Any]]:
    # Re-validate inside the worker; the route resolves the path up front.
    _resolve_workspace_relative_path(ree_id, script_relative_path)

    spec = ContainerScriptRun(
        workspace_path=workspace_dir(ree_id).resolve(),
        script_rel_path=script_relative_path,
        container_name=f"repo2ree-build-{run_id}",
        echo_label="build_runtime_script",
        sync_workspace_back=True,
    )

    _append_run_log(ree_id, run_id, "system", "info", f"Starting build run {run_id}")
    _append_run_log(
        ree_id, run_id, "system", "info", f"Starting container image {spec.image}"
    )
    _append_run_log(
        ree_id, run_id, "system", "info", f"Build script: {script_relative_path}"
    )

    outcome = run_script_in_container(
        spec,
        log=lambda stream, level, message: _append_run_log(
            ree_id, run_id, stream, level, message
        ),
        is_canceled=lambda: _is_cancel_requested(ree_id, run_id),
    )

    _append_run_log(
        ree_id,
        run_id,
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"Build run {outcome.status} (exit code {outcome.exit_code})",
    )

    outputs: dict[str, Any] = {
        "buildRuntimeScriptPath": script_relative_path,
        "dockerImage": spec.image,
    }
    if outcome.exit_code is not None:
        outputs["containerExitCode"] = outcome.exit_code
    return outcome.status, outputs


def create_build_run_state(
    ree_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    script_path = _require_non_empty_path(
        payload.build_runtime_script_path,
        "build_runtime_script_path",
    )
    return _start_background_run(
        ree_id=ree_id,
        operation="build",
        request_payload={"build_runtime_script_path": script_path},
        run_id_prefix="build",
        runner=lambda ws_id, run_id: _docker_build_run(
            ree_id=ws_id,
            run_id=run_id,
            script_relative_path=script_path,
        ),
    )


@build_runtime_router.post("/api/v1/rees/{ree_id}/build-runtime")
def create_workspace_build_runtime_run(
    ree_id: str, payload: CreateBuildRuntimeRunPayload
):
    run_state = create_build_run_state(ree_id, payload)
    return _run_summary(run_state)
