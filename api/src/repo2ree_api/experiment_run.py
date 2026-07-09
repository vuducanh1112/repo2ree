"""Thin HTTP layer for running a named experiment from a REE workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_protocol.command import RunExperimentArgs, RunExperimentCommand

# ================================================
# Router
# ================================================


experiment_run_router = APIRouter()


# ================================================
# Data models
# ================================================


class CreateExperimentRunPayload(BaseModel):
    """No fields yet — kept as the extension point for future run options."""

    model_config = ConfigDict(extra="forbid")


# ================================================
# Route handler
# ================================================


@experiment_run_router.post("/api/v1/rees/{ree_id}/experiments/{experiment_name}:run")
def create_experiment_run(
    ree_id: str,
    experiment_name: str,
    payload: CreateExperimentRunPayload,
):
    run_state = _create_experiment_run_state(ree_id, experiment_name)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _resolve_experiment_preflight(ree_id: str, experiment_name: str) -> None:
    """Validate the experiment exists and has a run script before starting a run."""
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")

    try:
        metadata = workbench_manager.get_ree_metadata(handle)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        ree = ReeIntent.from_metadata(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid REE intent: {exc}") from exc

    if not ree.runtime:
        raise HTTPException(
            status_code=400,
            detail="Runtime artifact is required before running experiments",
        )

    experiment = next((e for e in ree.experiments if e.name == experiment_name), None)
    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {experiment_name!r} not found",
        )
    if not experiment.run_script.strip():
        raise HTTPException(status_code=400, detail="Experiment has no run script")


def _create_experiment_run_state(
    ree_id: str,
    experiment_name: str,
) -> dict[str, Any]:
    _resolve_experiment_preflight(ree_id, experiment_name)

    return _start_single_command_run(
        ree_id,
        operation="experiment",
        command=RunExperimentCommand(args=RunExperimentArgs(experiment_name=experiment_name)),
        run_id_prefix="experiment",
        request_payload={"experimentName": experiment_name},
        canceled_message="Experiment run canceled",
        fallback_outputs={"subjectName": experiment_name},
    )
