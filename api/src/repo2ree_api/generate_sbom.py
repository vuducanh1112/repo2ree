from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree_core.sbom.generate_sbom import generate_sbom
from repo2ree_api.api_utils import WORKSPACE_CONTROL_PREFIXES, resolve_relative_path
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    WorkspacePatchPayload,
    patch_workspace,
    workspace_dir,
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


def resolve_sbom_runtime_path(
    ree_id: str,
    produced_runtime_path: str | None,
    params: dict[str, Any],
) -> str:
    runtime_path = produced_runtime_path or str(
        params.get("produced_runtime_path")
        or params.get("runtime_path")
        or params.get("runtime")
        or ""
    )
    runtime_path = runtime_path.strip()

    if not runtime_path:
        raise HTTPException(
            status_code=400, detail="produced_runtime_path is required for sbom runs"
        )

    runtime_abs_path = resolve_relative_path(
        workspace_dir(ree_id).resolve(),
        runtime_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )
    if not runtime_abs_path.exists() or not runtime_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Runtime tarball not found: {runtime_path}"
        )

    if not runtime_path.lower().endswith((".tar", ".tar.gz", ".tgz")):
        raise HTTPException(
            status_code=400,
            detail="SBOM generation currently supports runtime tarballs only (.tar, .tar.gz, or .tgz)",
        )

    return runtime_path


def generate_sbom_for_runtime(
    ree_id: str, runtime_relative_path: str
) -> dict[str, Any]:
    runtime_abs_path = resolve_relative_path(
        workspace_dir(ree_id).resolve(),
        runtime_relative_path,
        invalid_detail="Invalid workspace path",
        blocked_prefixes=WORKSPACE_CONTROL_PREFIXES,
    )
    output_dir = workspace_dir(ree_id)
    generated_sbom_path = generate_sbom(runtime_abs_path, output_dir)
    sbom_relative_path = "sbom.json"
    if generated_sbom_path.name != sbom_relative_path:
        raise RuntimeError(
            f"Unexpected generated SBOM filename: {generated_sbom_path.name}"
        )

    patch_workspace(
        ree_id,
        WorkspacePatchPayload(reePatch={"sbom": sbom_relative_path}),
    )

    return {
        "sbomRelativePath": sbom_relative_path,
        "runtimeRelativePath": runtime_relative_path,
        "format": "spdx-json",
    }


def create_generate_sbom_run_state(
    ree_id: str,
    payload: CreateGenerateSbomRunPayload,
) -> dict[str, Any]:
    runtime_path = resolve_sbom_runtime_path(
        ree_id=ree_id,
        produced_runtime_path=payload.produced_runtime_path,
        params={},
    )
    request_payload = {"produced_runtime_path": runtime_path}

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        _append_run_log(ree_id, run_id, "system", "info", f"Starting sbom run {run_id}")
        _append_run_log(
            ree_id, run_id, "system", "info", f"Runtime input: {runtime_path}"
        )
        if _is_cancel_requested(ree_id, run_id):
            _append_run_log(ree_id, run_id, "system", "warn", "SBOM run canceled")
            return "canceled", {
                "runtimeRelativePath": runtime_path,
                "format": "spdx-json",
            }
        try:
            outputs = generate_sbom_for_runtime(
                ree_id=ree_id,
                runtime_relative_path=runtime_path,
            )
        except Exception as exc:
            _append_run_log(
                ree_id,
                run_id,
                "system",
                "error",
                f"SBOM generation failed: {exc}",
            )
            raise
        _append_run_log(
            ree_id,
            run_id,
            "system",
            "info",
            f"Generated SBOM: {outputs['sbomRelativePath']}",
        )
        _append_run_log(ree_id, run_id, "system", "info", "SBOM run succeeded")
        return "succeeded", outputs

    return _start_background_run(
        ree_id=ree_id,
        operation="sbom",
        request_payload=request_payload,
        run_id_prefix="sbom",
        runner=_runner,
    )
