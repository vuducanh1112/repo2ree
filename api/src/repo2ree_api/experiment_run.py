"""Thin HTTP layer for running a named experiment from a REE workspace.

The run logic lives in ``repo2ree_core.experiment.run``. This module only
resolves the experiment from storage, wires the run-store callbacks, and
persists snapshot baselines back into the REE draft.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.ree import REE
from repo2ree_core.experiment.experiment import ExpectedOutput, Experiment
from repo2ree_core.experiment.run import run_experiment
from repo2ree_api.api_utils import WORKSPACE_CONTROL_PREFIXES, resolve_relative_path
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    ReeDraftPatchPayload,
    WorkspaceVersionConflictError,
    patch_ree_draft,
    read_workspace_metadata,
    workspace_dir,
)


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
# Storage adapters
# ================================================


def _resolve_experiment(
    ree_id: str, experiment_name: str
) -> tuple[Experiment, str, Path, str | None]:
    """Load the REE draft, returning the named experiment, runtime, and version."""
    try:
        metadata = read_workspace_metadata(ree_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ree_draft_raw = metadata.get("reeDraft") or {}
    try:
        ree = REE.model_validate(ree_draft_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid REE draft: {exc}"
        ) from exc
    runtime_path = ree.runtime.strip()
    if not runtime_path:
        raise HTTPException(
            status_code=400,
            detail="Runtime artifact is required before running experiments",
        )
    runtime_abs_path = resolve_relative_path(
        workspace_dir(ree_id).resolve(),
        runtime_path,
        invalid_detail="Invalid runtime path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )
    if not runtime_abs_path.exists() or not runtime_abs_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Runtime artifact not found: {runtime_path}",
        )
    for exp in ree.experiments:
        if exp.name == experiment_name:
            version = metadata.get("updatedAt")
            return (
                exp,
                runtime_path,
                runtime_abs_path,
                str(version) if version else None,
            )
    raise HTTPException(
        status_code=404,
        detail=f"Experiment {experiment_name!r} not found",
    )


def _persist_snapshot(
    ree_id: str,
    experiment_name: str,
    new_outputs: list[ExpectedOutput],
    *,
    expected_version: str | None,
) -> None:
    """Write the snapshot baselines back into the REE draft for *experiment_name*."""
    metadata = read_workspace_metadata(ree_id)
    ree_draft_raw = dict(metadata.get("reeDraft") or {})
    raw_experiments = list(ree_draft_raw.get("experiments") or [])
    updated = False
    for i, raw_exp in enumerate(raw_experiments):
        if raw_exp.get("name") == experiment_name:
            raw_experiments[i] = {
                **raw_exp,
                "outputs": [o.model_dump() for o in new_outputs],
            }
            updated = True
            break
    if not updated:
        return
    patch_ree_draft(
        ree_id,
        ReeDraftPatchPayload(
            reePatch={"experiments": raw_experiments},
            expectedVersion=expected_version,
        ),
    )


# ================================================
# Run-store wiring
# ================================================


def _create_experiment_run_state(
    ree_id: str,
    experiment_name: str,
    mode: Literal["verify", "snapshot"],
) -> dict[str, Any]:
    experiment, runtime_path, runtime_abs_path, expected_version = _resolve_experiment(
        ree_id, experiment_name
    )
    if not experiment.command.strip():
        raise HTTPException(status_code=400, detail="Experiment has no command to run")

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Experiment run canceled")
            return "canceled", {"experimentName": experiment_name, "mode": mode}

        outcome = run_experiment(
            workspace=workspace_dir(ree_id).resolve(),
            experiment=experiment,
            mode=mode,
            runtime_archive_path=runtime_abs_path,
            run_id=run_id,
            log=lambda stream, level, message: _append_run_log(
                ree_id, run_id, stream, level, message
            ),
            is_canceled=lambda: _is_cancel_requested(ree_id, run_id),
        )
        run_outputs = dict(outcome.run_outputs)
        run_outputs["runtimePath"] = runtime_path
        if outcome.snapshot_to_persist is not None:
            try:
                _persist_snapshot(
                    ree_id,
                    experiment_name,
                    outcome.snapshot_to_persist,
                    expected_version=expected_version,
                )
            except WorkspaceVersionConflictError as exc:
                _append_run_log(ree_id, run_id, "system", "error", str(exc))
                run_outputs["snapshotApplied"] = False
                run_outputs["snapshotMessage"] = (
                    "Snapshot was not saved because the draft changed during the run."
                )
                return "failed", run_outputs
            run_outputs["snapshotApplied"] = True
            run_outputs["snapshotMessage"] = (
                f"Saved {len(outcome.snapshot_to_persist)} baseline(s) to the draft."
            )
        return outcome.status, run_outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="experiment",
        request_payload={"experimentName": experiment_name, "mode": mode},
        run_id_prefix="experiment",
        runner=_runner,
    )
