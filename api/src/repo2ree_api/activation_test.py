from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)
from repo2ree_protocol import ActivationTestCommand
from repo2ree_protocol.command import ActivationTestArgs

# ================================================
# Router
# ================================================


activation_test_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateActivationTestRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@activation_test_router.post("/api/v1/rees/{ree_id}/activation-test")
def create_workspace_activation_test_run(ree_id: str, payload: CreateActivationTestRunPayload):
    run_state = create_activation_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def create_activation_run_state(
    ree_id: str,
    payload: CreateActivationTestRunPayload,
) -> dict[str, Any]:
    return _start_single_command_run(
        ree_id,
        operation="activation",
        command=ActivationTestCommand(args=ActivationTestArgs()),
        run_id_prefix="activation",
        request_payload={},
        canceled_message="Activation run canceled",
        fallback_outputs={"subjectName": "activation"},
    )
