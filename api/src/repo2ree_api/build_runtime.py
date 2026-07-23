from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol.command import BuildRuntimeCommand

# ================================================
# Router
# ================================================


build_runtime_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateBuildRuntimeRunPayload(CreateRunPayload):
    """Run the reserved build script. Takes no parameters of its own."""


# ================================================
# Route Handlers
# ================================================


@build_runtime_router.post(
    "/api/v1/rees/{ree_id}/build-runtime",
    operation_id="startBuild",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_build_runtime_run(ree_id: str, payload: CreateBuildRuntimeRunPayload):
    return run_summary(
        start_single_command_run(
            ree_id,
            operation="build",
            command=BuildRuntimeCommand(),
            run_id_prefix="build",
            request_payload={"build_runtime_script_path": RESERVED_BUILD_SCRIPT},
            canceled_message="Build run canceled",
            fallback_outputs={"build_runtime_script_path": RESERVED_BUILD_SCRIPT},
            idempotency_key=payload.idempotency_key,
        )
    )
