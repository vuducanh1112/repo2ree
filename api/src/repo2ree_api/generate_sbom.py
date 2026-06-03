from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from pathlib import Path

from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_protocol.command import GenerateSbomArgs, GenerateSbomCommand
from repo2ree_api.api_utils import WORKSPACE_CONTROL_PREFIXES, resolve_relative_path
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)


# ================================================
# Router
# ================================================


generate_sbom_router = APIRouter()


# ================================================
# Data Models
# ================================================


class CreateGenerateSbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_runtime_path: str
    idempotencyKey: str | None = None


# ================================================
# Route Handlers
# ================================================


@generate_sbom_router.post("/api/v1/rees/{ree_id}/generate-sbom")
def create_workspace_generate_sbom_run(
    ree_id: str, payload: CreateGenerateSbomRunPayload
):
    run_state = create_generate_sbom_run_state(ree_id, payload)
    return _run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _resolve_sbom_runtime_path(ree_id: str, produced_runtime_path: str) -> str:
    runtime_path = produced_runtime_path.strip()
    if not runtime_path:
        raise HTTPException(
            status_code=400, detail="produced_runtime_path is required for sbom runs"
        )
    # Validate the path string is safe (no traversal, no control prefixes). The
    # tarball lives in the workbench, so validate against a neutral virtual root
    # rather than any host directory; the handler re-resolves inside /ree.
    resolve_relative_path(
        Path("/__ree_workspace__"),
        runtime_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )
    if not runtime_path.lower().endswith((".tar", ".tar.gz", ".tgz")):
        raise HTTPException(
            status_code=400,
            detail="SBOM generation currently supports runtime tarballs only (.tar, .tar.gz, or .tgz)",
        )
    return runtime_path


def create_generate_sbom_run_state(
    ree_id: str,
    payload: CreateGenerateSbomRunPayload,
) -> dict[str, Any]:
    runtime_path = _resolve_sbom_runtime_path(ree_id, payload.produced_runtime_path)

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(ree_id, run_id, stream, level, message)

        if _is_cancel_requested(ree_id, run_id):
            _log("system", "warn", "SBOM run canceled")
            return "canceled", {"runtimeRelativePath": runtime_path}

        handle = workbench_manager.lookup(ree_id)
        if handle is None:
            _log("system", "error", "No workbench available for generate_sbom")
            return "failed", {}

        result = workbench_manager.dispatch_action(
            handle,
            GenerateSbomCommand(
                args=GenerateSbomArgs(produced_runtime_path=runtime_path)
            ),
            run_id,
            _log,
        )
        return result.status, result.outputs or {"runtimeRelativePath": runtime_path}

    return _start_background_run(
        ree_id=ree_id,
        operation="sbom",
        request_payload={"produced_runtime_path": runtime_path},
        run_id_prefix="sbom",
        runner=_runner,
    )
