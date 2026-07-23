from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_protocol.command import CrossCheckSbomArgs, CrossCheckSbomCommand

# ================================================
# Router
# ================================================


cross_check_sbom_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateCrossCheckSbomRunPayload(CreateRunPayload):
    """Cross-check the recorded SBOM against the built runtime. No parameters."""


# ================================================
# Route Handlers
# ================================================


@cross_check_sbom_router.post(
    "/api/v1/rees/{ree_id}/cross-check-sbom",
    operation_id="startSbomCrossCheck",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_cross_check_sbom_run(ree_id: str, payload: CreateCrossCheckSbomRunPayload):
    return run_summary(
        start_single_command_run(
            ree_id,
            operation="crosscheck",
            command=CrossCheckSbomCommand(args=CrossCheckSbomArgs()),
            run_id_prefix="crosscheck",
            request_payload={},
            canceled_message="SBOM cross-check run canceled",
            idempotency_key=payload.idempotency_key,
        )
    )
