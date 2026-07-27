from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_commands import require_handle
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_core.repo_profiler.reproducibility_report import ReproducibilityReport
from repo2ree_protocol.command import (
    EvaluateDependencyScoreArgs,
    EvaluateDependencyScoreCommand,
)

# ================================================
# Router
# ================================================


evaluate_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateEvaluateRunPayload(CreateRunPayload):
    strict: bool = False


# ================================================
# Route Handlers
# ================================================


@evaluate_router.post(
    "/api/v1/rees/{ree_id}/evaluate",
    operation_id="startEvaluate",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_evaluate_run(ree_id: str, payload: CreateEvaluateRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="evaluate",
                command=EvaluateDependencyScoreCommand(args=EvaluateDependencyScoreArgs(strict=payload.strict)),
                run_id_prefix="evaluate",
                request_payload={"strict": bool(payload.strict)},
                canceled_message="Evaluate run canceled",
                idempotency_key=payload.idempotency_key,
            )
        )
    )


_REPORT_FILENAME = "reproducibility-report.json"


@evaluate_router.get(
    "/api/v1/rees/{ree_id}/evaluate/report",
    operation_id="getEvaluateReport",
    response_model=ReproducibilityReport,
    responses=ERROR_RESPONSES,
)
def get_workspace_evaluate_report(ree_id: str) -> dict[str, Any]:
    """The persisted evaluate-run report artifact."""
    # An unknown or unreachable REE is resolved first, so "no report yet" is
    # never how a caller learns their REE is gone (404) or its workbench is
    # down (503).
    handle = require_handle(ree_id)
    try:
        data = workbench_manager.read_artifact_bytes(handle, _REPORT_FILENAME)
        report: dict[str, Any] = json.loads(data)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail="No reproducibility report; run evaluate first",
        ) from exc
