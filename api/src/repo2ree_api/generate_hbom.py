from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_protocol import GenerateHbomCommand

# ================================================
# Router
# ================================================


generate_hbom_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateGenerateHbomRunPayload(CreateRunPayload):
    """Profile the workbench host's hardware. Takes no parameters of its own."""


# ================================================
# Route Handlers
# ================================================


@generate_hbom_router.post(
    "/api/v1/rees/{ree_id}/generate-hbom",
    operation_id="startHbomGeneration",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_generate_hbom_run(ree_id: str, payload: CreateGenerateHbomRunPayload):
    return run_summary(
        start_single_command_run(
            ree_id,
            operation="hbom",
            command=GenerateHbomCommand(),
            run_id_prefix="hbom",
            request_payload={},
            canceled_message="HBOM run canceled",
            idempotency_key=payload.idempotency_key,
        )
    )
