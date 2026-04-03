from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from repo2ree.service.api.build_runtime import (
    _persist_run_state,
    _require_workspace,
    _run_summary,
    _utc_now,
)
from repo2ree.service.storage.workspace_files import (
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

    return {
        "sbomRelativePath": sbom_relative_path,
        "runtimeRelativePath": runtime_relative_path,
        "format": "spdx-json",
    }


def create_generate_sbom_run_state(
    workspace_id: str,
    payload: CreateGenerateSbomRunPayload,
) -> dict[str, Any]:
    _require_workspace(workspace_id)
    created_at = _utc_now()
    started_at = created_at
    run_id = f"sbom-{uuid4().hex}"
    runtime_path = resolve_sbom_runtime_path(
        workspace_id=workspace_id,
        produced_runtime_path=payload.produced_runtime_path,
        params={},
    )
    outputs = generate_dummy_sbom_for_runtime(
        workspace_id=workspace_id,
        runtime_relative_path=runtime_path,
    )
    request_payload = {"produced_runtime_path": runtime_path}
    logs = [
        {
            "seq": 1,
            "ts": _utc_now(),
            "stream": "system",
            "level": "info",
            "message": f"Starting sbom run {run_id}",
        },
        {
            "seq": 2,
            "ts": _utc_now(),
            "stream": "system",
            "level": "info",
            "message": f"Runtime input: {runtime_path}",
        },
        {
            "seq": 3,
            "ts": _utc_now(),
            "stream": "system",
            "level": "info",
            "message": f"Generated SBOM: {outputs['sbomRelativePath']}",
        },
        {
            "seq": 4,
            "ts": _utc_now(),
            "stream": "system",
            "level": "info",
            "message": "SBOM run succeeded",
        },
    ]
    return _persist_run_state(
        workspace_id=workspace_id,
        run_id=run_id,
        operation="sbom",
        status="succeeded",
        created_at=created_at,
        started_at=started_at,
        outputs=outputs,
        logs=logs,
        request_payload=request_payload,
    )


@generate_sbom_router.post("/api/v1/workspaces/{workspace_id}/generate-sbom")
def create_workspace_generate_sbom_run(
    workspace_id: str, payload: CreateGenerateSbomRunPayload
):
    run_state = create_generate_sbom_run_state(workspace_id, payload)
    return _run_summary(run_state)
