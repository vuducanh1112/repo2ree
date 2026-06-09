from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_protocol.command import BuildRuntimeArgs, BuildRuntimeCommand
from repo2ree_api.api_utils import require_non_empty_path
from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
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

    return _start_single_command_run(
        ree_id,
        operation="build",
        command=BuildRuntimeCommand(
            args=BuildRuntimeArgs(build_runtime_script_path=script_path)
        ),
        run_id_prefix="build",
        request_payload={"build_runtime_script_path": script_path},
        canceled_message="Build run canceled",
        fallback_outputs={"buildRuntimeScriptPath": script_path},
    )
