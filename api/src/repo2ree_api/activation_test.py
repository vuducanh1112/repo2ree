from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_protocol import ActivationTestCommand
from repo2ree_protocol.command import ActivationTestArgs

# ================================================
# Router
# ================================================


activation_test_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateActivationTestRunPayload(CreateRunPayload):
    """Run the reserved activation script. Takes no parameters of its own."""


# ================================================
# Route Handlers
# ================================================


@activation_test_router.post(
    "/api/v1/rees/{ree_id}/activation-test",
    operation_id="startActivationTest",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_activation_test_run(ree_id: str, payload: CreateActivationTestRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="activation",
                command=ActivationTestCommand(args=ActivationTestArgs()),
                run_id_prefix="activation",
                request_payload={},
                canceled_message="Activation run canceled",
                fallback_outputs={"subject_name": "activation"},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
