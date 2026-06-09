from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_protocol import GenerateHbomCommand
from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)


# ================================================
# Router
# ================================================


generate_hbom_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateGenerateHbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@generate_hbom_router.post("/api/v1/rees/{ree_id}/generate-hbom")
def create_workspace_generate_hbom_run(
    ree_id: str, payload: CreateGenerateHbomRunPayload
):
    run_state = create_generate_hbom_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def create_generate_hbom_run_state(
    ree_id: str,
    payload: CreateGenerateHbomRunPayload,
) -> dict[str, Any]:
    return _start_single_command_run(
        ree_id,
        operation="hbom",
        command=GenerateHbomCommand(),
        run_id_prefix="hbom",
        request_payload={"idempotencyKey": payload.idempotencyKey},
        canceled_message="HBOM run canceled",
    )
