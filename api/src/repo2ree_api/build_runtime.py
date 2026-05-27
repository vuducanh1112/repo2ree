from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_core.working_environment import run_workspace_script
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
    workspace = workspace_dir(ree_id).resolve()

    # Validate path before provisioning the environment.
    resolve_relative_path(
        workspace,
        script_relative_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )

    def _log(stream: str, level: str, message: str) -> None:
        _append_run_log(ree_id, run_id, stream, level, message)

    _log("system", "info", f"Starting build run {run_id}")
    _log("system", "info", f"Build script: {script_relative_path}")

    outcome = run_workspace_script(
        workspace=workspace,
        script_rel_path=script_relative_path,
        run_id=run_id,
        log=_log,
        is_canceled=lambda: _is_cancel_requested(ree_id, run_id),
        echo_label="build_runtime_script",
        sync_out_on_success=True,
    )

    _log(
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"Build run {outcome.status} (exit code {outcome.exit_code})",
    )

    outputs: dict[str, Any] = {"buildRuntimeScriptPath": script_relative_path}
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
        runner=lambda ree_id, run_id: _docker_build_run(
            ree_id=ree_id,
            run_id=run_id,
            script_relative_path=script_path,
        ),
    )
