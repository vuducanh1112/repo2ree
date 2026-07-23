"""Thin HTTP layer for running a named experiment from a REE workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.contracts import ERROR_RESPONSES, RunSummary
from repo2ree_api.run_management import (
    run_summary,
    start_single_command_run,
)
from repo2ree_protocol.command import RunExperimentArgs, RunExperimentCommand

# ================================================
# Router
# ================================================


experiment_run_router = APIRouter(tags=["runs"])


# ================================================
# Data models
# ================================================


class CreateExperimentRunPayload(BaseModel):
    """No fields yet — kept as the extension point for future run options."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = None


# ================================================
# Route handler
# ================================================


@experiment_run_router.post(
    "/api/v1/rees/{ree_id}/experiments/{experiment_name}:run",
    operation_id="startExperiment",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_experiment_run(
    ree_id: str,
    experiment_name: str,
    payload: CreateExperimentRunPayload,
):
    run_state = _create_experiment_run_state(ree_id, experiment_name, payload.idempotency_key)
    return run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _create_experiment_run_state(
    ree_id: str,
    experiment_name: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    # No host-side resolution preflight: reading the intent costs a synchronous
    # round-trip into the workbench (~600ms on the click path) to re-check rules
    # the in-workbench handler applies authoritatively anyway — the intent can
    # change between the two, so only the workbench's verdict ever counted. An
    # unresolvable experiment now surfaces as a failed run carrying the same
    # message, exactly as the activation route already behaved.
    return start_single_command_run(
        ree_id,
        operation="experiment",
        command=RunExperimentCommand(args=RunExperimentArgs(experiment_name=experiment_name)),
        run_id_prefix="experiment",
        request_payload={"experiment_name": experiment_name},
        canceled_message="Experiment run canceled",
        fallback_outputs={"subject_name": experiment_name},
        idempotency_key=idempotency_key,
    )
