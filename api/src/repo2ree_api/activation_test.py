from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.run_management import (
    _run_summary,
    _start_single_command_run,
)
from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_protocol import ActivationTestCommand
from repo2ree_protocol.command import ActivationTestArgs

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
def create_workspace_activation_test_run(ree_id: str, payload: CreateActivationTestRunPayload):
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

    ree_intent = dict(metadata.get("reeIntent") or {})
    script_path = str(ree_intent.get("activation_script") or "").strip()

    if not script_path:
        raise HTTPException(status_code=400, detail="activation_script is required")
    return script_path


def create_activation_run_state(
    ree_id: str,
    payload: CreateActivationTestRunPayload,
) -> dict[str, Any]:
    activation_script_path = _resolve_activation_script_path(ree_id, payload.activation_script_path)

    return _start_single_command_run(
        ree_id,
        operation="activation",
        command=ActivationTestCommand(args=ActivationTestArgs(activation_script_path=activation_script_path)),
        run_id_prefix="activation",
        request_payload={"activation_script_path": activation_script_path},
        canceled_message="Activation run canceled",
        fallback_outputs={"activationScriptPath": activation_script_path},
    )
