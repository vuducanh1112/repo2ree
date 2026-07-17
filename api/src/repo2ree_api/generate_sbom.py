from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_api.api_utils import WORKSPACE_CONTROL_PREFIXES, resolve_relative_path
from repo2ree_api.contracts import ERROR_RESPONSES, RunSummary
from repo2ree_api.run_management import (
    run_summary,
    start_single_command_run,
)
from repo2ree_protocol.command import GenerateSbomArgs, GenerateSbomCommand

# ================================================
# Router
# ================================================


generate_sbom_router = APIRouter(tags=["runs"])


# ================================================
# Data Models
# ================================================


class CreateGenerateSbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_runtime_path: str
    idempotency_key: str | None = None


# ================================================
# Route Handlers
# ================================================


@generate_sbom_router.post(
    "/api/v1/rees/{ree_id}/generate-sbom",
    operation_id="startSbomGeneration",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_generate_sbom_run(ree_id: str, payload: CreateGenerateSbomRunPayload):
    run_state = create_generate_sbom_run_state(ree_id, payload)
    return run_summary(run_state)


# ================================================
# Helpers
# ================================================


def _resolve_sbom_runtime_path(ree_id: str, produced_runtime_path: str) -> str:
    runtime_path = produced_runtime_path.strip()
    if not runtime_path:
        raise HTTPException(status_code=400, detail="produced_runtime_path is required for sbom runs")
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

    return start_single_command_run(
        ree_id,
        operation="sbom",
        command=GenerateSbomCommand(args=GenerateSbomArgs(produced_runtime_path=runtime_path)),
        run_id_prefix="sbom",
        request_payload={"produced_runtime_path": runtime_path},
        canceled_message="SBOM run canceled",
        fallback_outputs={"runtime_relative_path": runtime_path},
        idempotency_key=payload.idempotency_key,
    )
