from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.working_environment import run_workspace_script
from repo2ree_api.api_utils import WORKSPACE_CONTROL_PREFIXES, resolve_relative_path
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    read_workspace_metadata,
    workspace_dir,
)


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


def resolve_activation_script_path(
    ree_id: str,
    *,
    params: dict[str, Any] | None = None,
    activation_script_path: str | None = None,
) -> str:
    metadata = read_workspace_metadata(ree_id)
    ree_draft = dict(metadata.get("reeDraft") or {})
    params = dict(params or {})
    script_path = (
        activation_script_path
        or str(
            params.get("activation_script")
            or params.get("activation_script_path")
            or ree_draft.get("activation_script")
            or ree_draft.get("validate_runtime_reproducibility_script")
            or ""
        ).strip()
    )

    if not script_path:
        raise HTTPException(status_code=400, detail="activation_script is required")

    script_abs_path = resolve_relative_path(
        workspace_dir(ree_id).resolve(),
        script_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )
    if not script_abs_path.exists() or not script_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Activation script not found: {script_path}"
        )

    return script_path


def run_activation_test(
    ree_id: str,
    run_id: str,
    activation_script_path: str,
) -> tuple[str, dict[str, Any]]:
    workspace = workspace_dir(ree_id).resolve()

    # Re-validate inside the worker before provisioning the environment.
    resolve_relative_path(
        workspace,
        activation_script_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )

    def _log(stream: str, level: str, message: str) -> None:
        _append_run_log(ree_id, run_id, stream, level, message)

    _log("system", "info", f"Starting activation run {run_id}")
    _log("system", "info", f"Activation script: {activation_script_path}")

    outcome = run_workspace_script(
        workspace=workspace,
        script_rel_path=activation_script_path,
        run_id=run_id,
        log=_log,
        is_canceled=lambda: _is_cancel_requested(ree_id, run_id),
        echo_label="activation_script",
    )

    _log(
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"Activation run {outcome.status} (exit code {outcome.exit_code})",
    )

    outputs: dict[str, Any] = {"activationScriptPath": activation_script_path}
    if outcome.exit_code is not None:
        outputs["containerExitCode"] = outcome.exit_code
    return outcome.status, outputs


def create_activation_run_state(
    ree_id: str,
    payload: CreateActivationTestRunPayload,
) -> dict[str, Any]:
    activation_script_path = resolve_activation_script_path(
        ree_id,
        params={},
        activation_script_path=payload.activation_script_path,
    )
    request_payload = {"activation_script_path": activation_script_path}

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "Activation run canceled")
            return "canceled", {"activationScriptPath": activation_script_path}
        return run_activation_test(
            ree_id=ree_id,
            run_id=run_id,
            activation_script_path=activation_script_path,
        )

    return _start_background_run(
        ree_id=ree_id,
        operation="activation",
        request_payload=request_payload,
        run_id_prefix="activation",
        runner=_runner,
    )
