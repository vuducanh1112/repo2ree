"""Thin HTTP layer for running a named experiment from a REE workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.contracts import ERROR_RESPONSES, RunSummary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import (
    run_summary,
    start_single_command_run,
)
from repo2ree_core.experiment.resolve import (
    ExperimentNotFoundError,
    RunnableResolutionError,
    resolve_experiment_runnable,
)
from repo2ree_core.workspace.model import WorkspaceMetadata
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


def _resolve_experiment_preflight(ree_id: str, experiment_name: str) -> None:
    """Reject a run that cannot start, with a synchronous 4xx instead of a failed run.

    Advisory only: the intent can change between this check and dispatch, so the
    in-workbench handler applies the same core rules authoritatively.
    """
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")

    try:
        metadata = workbench_manager.get_ree_metadata(handle)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        ree = WorkspaceMetadata.model_validate(metadata).ree_intent
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid REE intent: {exc}") from exc

    try:
        resolve_experiment_runnable(ree, experiment_name)
    except ExperimentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RunnableResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _create_experiment_run_state(
    ree_id: str,
    experiment_name: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    _resolve_experiment_preflight(ree_id, experiment_name)

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
