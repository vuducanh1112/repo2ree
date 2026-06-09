from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_protocol.command import (
    EvaluateDependencyScoreArgs,
    EvaluateDependencyScoreCommand,
)

# ================================================
# Router
# ================================================


evaluate_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateEvaluateRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = False
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@evaluate_router.post("/api/v1/rees/{ree_id}/evaluate")
def create_workspace_evaluate_run(ree_id: str, payload: CreateEvaluateRunPayload):
    run_state = create_evaluate_run_state(ree_id, payload)
    return _run_summary(run_state)


_REPORT_FILENAME = "reproducibility-report.json"


@evaluate_router.get("/api/v1/rees/{ree_id}/evaluate/report")
def get_workspace_evaluate_report(ree_id: str) -> dict[str, Any]:
    handle = workbench_manager.lookup(ree_id)
    if handle is not None:
        try:
            data = workbench_manager.read_artifact_bytes(handle, _REPORT_FILENAME)
            return json.loads(data)
        except Exception as exc:
            raise HTTPException(
                status_code=404,
                detail="No reproducibility report; run evaluate first",
            ) from exc
    raise HTTPException(status_code=404, detail="No reproducibility report; run evaluate first")


# ================================================
# Helpers
# ================================================


def create_evaluate_run_state(
    ree_id: str,
    payload: CreateEvaluateRunPayload,
) -> dict[str, Any]:
    request_payload = {"strict": bool(payload.strict)}

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "Evaluate run canceled")
            return "canceled", {}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for evaluate")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle,
            EvaluateDependencyScoreCommand(args=EvaluateDependencyScoreArgs(strict=payload.strict)),
            run_id,
            _log,
        )
        return result.status, result.outputs or {}

    return _start_background_run(
        ree_id=ree_id,
        operation="evaluate",
        request_payload=request_payload,
        run_id_prefix="evaluate",
        runner=_runner,
    )
