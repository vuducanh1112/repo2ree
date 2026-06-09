"""Thin HTTP layer for running a named experiment from a REE workspace."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.workbench.deps import workbench_manager
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
    model_config = ConfigDict(extra="forbid")

    mode: Literal["verify", "snapshot"] = "verify"


# ================================================
# Route handler
# ================================================


@experiment_run_router.post("/api/v1/rees/{ree_id}/experiments/{experiment_name}:run")
def create_experiment_run(
    ree_id: str,
    experiment_name: str,
    payload: CreateExperimentRunPayload,
):
    run_state = _create_experiment_run_state(ree_id, experiment_name, payload.mode)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _resolve_experiment_preflight(ree_id: str, experiment_name: str) -> None:
    """Validate the experiment exists and has a command before starting a run."""
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

    if not ree.runtime.strip():
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
    if not experiment.command.strip():
        raise HTTPException(status_code=400, detail="Experiment has no command to run")


def _create_experiment_run_state(
    ree_id: str,
    experiment_name: str,
    mode: Literal["verify", "snapshot"],
) -> dict[str, Any]:
    _resolve_experiment_preflight(ree_id, experiment_name)

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "Experiment run canceled")
            return "canceled", {"experimentName": experiment_name, "mode": mode}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for run_experiment")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle,
            RunExperimentCommand(args=RunExperimentArgs(experiment_name=experiment_name, mode=mode)),
            run_id,
            _log,
        )
        return result.status, result.outputs or {
            "experimentName": experiment_name,
            "mode": mode,
        }

    return _start_background_run(
        ree_id=ree_id,
        operation="experiment",
        request_payload={"experimentName": experiment_name, "mode": mode},
        run_id_prefix="experiment",
        runner=_runner,
    )
