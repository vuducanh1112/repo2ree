from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree.service.api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree.service.storage.workspace_files import (
    WorkspacePatchPayload,
    patch_workspace,
    read_workspace_metadata,
    workspace_dir,
    write_file_content,
)


generate_sbom_router = APIRouter()


class CreateGenerateSbomRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_runtime_path: str
    idempotencyKey: str | None = None


def _resolve_workspace_relative_path(workspace_id: str, relative_path: str) -> Path:
    root = workspace_dir(workspace_id).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid workspace path") from exc
    if candidate.name.startswith(".workspace") or candidate.name.startswith(".upload."):
        raise HTTPException(status_code=400, detail="Invalid workspace path")
    return candidate


def resolve_sbom_runtime_path(
    workspace_id: str,
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

    runtime_abs_path = _resolve_workspace_relative_path(workspace_id, runtime_path)
    if not runtime_abs_path.exists() or not runtime_abs_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"Runtime tarball not found: {runtime_path}"
        )

    if not runtime_path.lower().endswith((".tar.gz", ".tgz")):
        raise HTTPException(
            status_code=400,
            detail="SBOM generation currently supports runtime tarballs only (.tar.gz or .tgz)",
        )

    return runtime_path


def generate_dummy_sbom_for_runtime(
    workspace_id: str, runtime_relative_path: str
) -> dict[str, Any]:
    metadata = read_workspace_metadata(workspace_id)
    ree_draft = dict(metadata.get("reeDraft") or {})
    ree_name = str(ree_draft.get("name") or f"workspace-{workspace_id[:8]}")

    sbom_payload = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{ree_name}-sbom",
        "documentNamespace": f"https://example.org/repo2ree/sbom/{workspace_id}",
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: repo2ree dummy sbom generator"],
        },
        "runtime": runtime_relative_path,
        "packages": [
            {
                "SPDXID": "SPDXRef-root-runtime",
                "name": Path(runtime_relative_path).name,
                "versionInfo": "unknown",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
            }
        ],
    }

    sbom_relative_path = "sbom.json"
    write_file_content(
        workspace_id,
        sbom_relative_path,
        json.dumps(sbom_payload, indent=2),
    )
    patch_workspace(
        workspace_id,
        WorkspacePatchPayload(reePatch={"sbom": sbom_relative_path}),
    )

    return {
        "sbomRelativePath": sbom_relative_path,
        "runtimeRelativePath": runtime_relative_path,
        "format": "spdx-json",
    }


def create_generate_sbom_run_state(
    workspace_id: str,
    payload: CreateGenerateSbomRunPayload,
) -> dict[str, Any]:
    runtime_path = resolve_sbom_runtime_path(
        workspace_id=workspace_id,
        produced_runtime_path=payload.produced_runtime_path,
        params={},
    )
    request_payload = {"produced_runtime_path": runtime_path}

    def _runner(ws_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        _append_run_log(ws_id, run_id, "system", "info", f"Starting sbom run {run_id}")
        _append_run_log(
            ws_id, run_id, "system", "info", f"Runtime input: {runtime_path}"
        )
        if _is_cancel_requested(ws_id, run_id):
            _append_run_log(ws_id, run_id, "system", "warn", "SBOM run canceled")
            return "canceled", {
                "runtimeRelativePath": runtime_path,
                "format": "spdx-json",
            }
        outputs = generate_dummy_sbom_for_runtime(
            workspace_id=ws_id,
            runtime_relative_path=runtime_path,
        )
        _append_run_log(
            ws_id,
            run_id,
            "system",
            "info",
            f"Generated SBOM: {outputs['sbomRelativePath']}",
        )
        _append_run_log(ws_id, run_id, "system", "info", "SBOM run succeeded")
        return "succeeded", outputs

    return _start_background_run(
        workspace_id=workspace_id,
        operation="sbom",
        request_payload=request_payload,
        run_id_prefix="sbom",
        runner=_runner,
    )


@generate_sbom_router.post("/api/v1/workspaces/{workspace_id}/generate-sbom")
def create_workspace_generate_sbom_run(
    workspace_id: str, payload: CreateGenerateSbomRunPayload
):
    run_state = create_generate_sbom_run_state(workspace_id, payload)
    return _run_summary(run_state)
