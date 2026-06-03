from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_protocol import ActivationTestCommand
from repo2ree_protocol.command import ActivationTestArgs
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


activation_test_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateActivationTestRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_script_path: str
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@activation_test_router.post("/api/v1/rees/{ree_id}/activation-test")
def create_workspace_activation_test_run(
    ree_id: str, payload: CreateActivationTestRunPayload
):
    run_state = create_activation_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _resolve_activation_script_path(
    ree_id: str,
    activation_script_path: str | None,
) -> str:
    """Return the script path, falling back to the value stored in the REE draft."""
    if activation_script_path and activation_script_path.strip():
        return activation_script_path.strip()

    handle = workbench_manager.lookup(ree_id)
    if handle is not None:
        try:
            metadata = workbench_manager.get_ree_metadata(handle)
        except Exception:
            metadata = {}
    else:
        metadata = {}

    ree_draft = dict(metadata.get("reeDraft") or {})
    script_path = str(
        ree_draft.get("activation_script")
        or ree_draft.get("validate_runtime_reproducibility_script")
        or ""
    ).strip()

    if not script_path:
        raise HTTPException(status_code=400, detail="activation_script is required")
    return script_path


def create_activation_run_state(
    ree_id: str,
    payload: CreateActivationTestRunPayload,
) -> dict[str, Any]:
    activation_script_path = _resolve_activation_script_path(
        ree_id, payload.activation_script_path
    )

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "Activation run canceled")
            return "canceled", {"activationScriptPath": activation_script_path}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for activation_test")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle,
            ActivationTestCommand(
                args=ActivationTestArgs(activation_script_path=activation_script_path)
            ),
            run_id,
            _log,
        )
        return result.status, result.outputs or {
            "activationScriptPath": activation_script_path
        }

    return _start_background_run(
        ree_id=ree_id,
        operation="activation",
        request_payload={"activation_script_path": activation_script_path},
        run_id_prefix="activation",
        runner=_runner,
    )
