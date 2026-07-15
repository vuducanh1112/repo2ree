from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.contracts import ERROR_RESPONSES, RunSummary
from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)
from repo2ree_protocol.command import CrossCheckSbomArgs, CrossCheckSbomCommand

# ================================================
# Router
# ================================================


cross_check_sbom_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateCrossCheckSbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str | None = None


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
    run_state = create_cross_check_sbom_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def create_cross_check_sbom_run_state(
    ree_id: str,
    payload: CreateCrossCheckSbomRunPayload,
) -> dict[str, Any]:
    return _start_single_command_run(
        ree_id,
        operation="crosscheck",
        command=CrossCheckSbomCommand(args=CrossCheckSbomArgs()),
        run_id_prefix="crosscheck",
        request_payload={},
        canceled_message="SBOM cross-check run canceled",
        idempotency_key=payload.idempotencyKey,
    )
