from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol.command import BuildRuntimeCommand

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
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@build_runtime_router.post("/api/v1/rees/{ree_id}/build-runtime")
def create_workspace_build_runtime_run(ree_id: str, payload: CreateBuildRuntimeRunPayload):
    run_state = create_build_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def create_build_run_state(
    ree_id: str,
    payload: CreateBuildRuntimeRunPayload,
) -> dict[str, Any]:
    # The build always runs the reserved, REE-owned build script.
    del payload  # no author-configurable inputs

    return _start_single_command_run(
        ree_id,
        operation="build",
        command=BuildRuntimeCommand(),
        run_id_prefix="build",
        request_payload={"build_runtime_script_path": RESERVED_BUILD_SCRIPT},
        canceled_message="Build run canceled",
        fallback_outputs={"buildRuntimeScriptPath": RESERVED_BUILD_SCRIPT},
    )
