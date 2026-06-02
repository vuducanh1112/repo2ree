from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_core.envelope import GenerateHbomCommand
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.workbench.deps import workbench_manager


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
    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "HBOM run canceled")
            return "canceled", {}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for generate_hbom")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle, GenerateHbomCommand(), run_id, _log
        )
        return result.status, result.outputs or {}

    return _start_background_run(
        ree_id=ree_id,
        operation="hbom",
        request_payload={"idempotencyKey": payload.idempotencyKey},
        run_id_prefix="hbom",
        runner=_runner,
    )
