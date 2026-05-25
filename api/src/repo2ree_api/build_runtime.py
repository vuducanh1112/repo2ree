from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_core.container.run_script import (
    ContainerScriptRun,
    run_script_in_container,
)
from repo2ree_api.api_utils import (
    WORKSPACE_CONTROL_PREFIXES,
    require_non_empty_path,
    resolve_relative_path,
)
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _start_background_run,
    _run_summary,
)
from repo2ree_api.storage.workspace_files import workspace_dir


# ================================================
# Router
# ================================================


build_runtime_router = APIRouter()


# ================================================
# Data Models
# ================================================


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBuildRuntimeRunPayload(_StrictRequestModel):
    build_runtime_script_path: str
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@build_runtime_router.post("/api/v1/rees/{ree_id}/build-runtime")
def create_workspace_build_runtime_run(
    ree_id: str, payload: CreateBuildRuntimeRunPayload
):
    run_state = create_build_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _docker_build_run(
    ree_id: str,
    run_id: str,
    script_relative_path: str,
) -> tuple[str, dict[str, Any]]:
    # Validate inside the worker before launching the container.
    resolve_relative_path(
        workspace_dir(ree_id).resolve(),
        script_relative_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )

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
    script_path = require_non_empty_path(
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
