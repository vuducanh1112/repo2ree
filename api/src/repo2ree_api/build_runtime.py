from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_protocol.command import BuildRuntimeArgs, BuildRuntimeCommand
from repo2ree_api.api_utils import require_non_empty_path
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _start_background_run,
    _run_summary,
)


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


def create_build_run_state(
    ree_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    script_path = require_non_empty_path(
        payload.build_runtime_script_path,
        "build_runtime_script_path",
    )

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "Build run canceled")
            return "canceled", {"buildRuntimeScriptPath": script_path}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for build_runtime")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle,
            BuildRuntimeCommand(
                args=BuildRuntimeArgs(build_runtime_script_path=script_path)
            ),
            run_id,
            _log,
        )
        return result.status, result.outputs or {"buildRuntimeScriptPath": script_path}

    return _start_background_run(
        ree_id=ree_id,
        operation="build",
        request_payload={"build_runtime_script_path": script_path},
        run_id_prefix="build",
        runner=_runner,
    )
