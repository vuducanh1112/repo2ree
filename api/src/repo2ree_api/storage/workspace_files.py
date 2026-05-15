"""Thin API adapter for workspace and REE operations.

All business logic and filesystem I/O lives in
``repo2ree_core.storage.workspace_ops``. This module re-exports every
symbol that the rest of the API package imports, binding the storage root
to ``service_settings.WORKSPACE_STORAGE_DIR``.

Payload models stay here because they are FastAPI request/response shapes
and belong in the API layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

import repo2ree_core.storage.workspace_ops as _ops
from repo2ree_api.settings import service_settings
from repo2ree_core.workspace.bundle import (
    REE_MANIFEST_ENTRY_PATH,
    REE_ROOT_PREFIX,
)


# ---------------------------------------------------------------------------
# Re-exported constants
# ---------------------------------------------------------------------------

__all__ = [
    "REE_MANIFEST_ENTRY_PATH",
    "REE_ROOT_PREFIX",
    # Payload models
    "WorkspaceCreatePayload",
    "WorkspacePatchPayload",
    "ReeDraftPatchPayload",
    "SourceAcquirePayload",
    "UploadInitPayload",
    "SourceUploadCompletePayload",
    "WorkspaceFileContentPayload",
    # Wrappers
    "workspace_root",
    "ensure_workspace_root",
    "workspace_exists",
    "workspace_dir",
    "artifact_dir",
    "ree_dir",
    "metadata_path",
    "ree_manifest_path",
    "read_workspace_metadata",
    "list_workspace_metadata",
    "get_workspace",
    "list_files",
    "create_workspace",
    "patch_ree_draft",
    "patch_workspace",
    "delete_workspace",
    "read_file_content",
    "read_file_bytes",
    "write_file_content",
    "delete_file_content",
    "acquire_source",
    "init_source_upload",
    "store_source_upload_bytes",
    "complete_source_upload",
    "remove_source",
    "build_workspace_ree_archive",
]


# ---------------------------------------------------------------------------
# Request / response payload models
# ---------------------------------------------------------------------------


class WorkspaceCreatePayload(BaseModel):
    sourceMode: Literal["url", "upload", "demo"]
    originUrl: str | None = None
    sourceType: Literal["git", "tarball", "zip"] | None = None
    name: str | None = None


class WorkspacePatchPayload(BaseModel):
    reePatch: dict[str, Any] = Field(default_factory=dict)
    expectedVersion: str | None = None


class ReeDraftPatchPayload(BaseModel):
    reePatch: dict[str, Any] = Field(default_factory=dict)
    expectedVersion: str | None = None


class SourceAcquirePayload(BaseModel):
    originUrl: str
    sourceType: Literal["git", "tarball", "zip"]


class UploadInitPayload(BaseModel):
    fileName: str
    size: int
    contentType: str


class SourceUploadCompletePayload(BaseModel):
    uploadToken: str
    archiveName: str


class WorkspaceFileContentPayload(BaseModel):
    path: str
    content: str
    ifMatch: str | None = None


# ---------------------------------------------------------------------------
# Storage root accessor
# ---------------------------------------------------------------------------


def workspace_root() -> Path:
    return service_settings.WORKSPACE_STORAGE_DIR


def ensure_workspace_root() -> None:
    workspace_root().mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Path accessors
# ---------------------------------------------------------------------------


def workspace_exists(ree_id: str) -> bool:
    return _ops.workspace_exists(workspace_root(), ree_id)


def workspace_dir(ree_id: str) -> Path:
    return _ops.workspace_dir(workspace_root(), ree_id)


def artifact_dir(ree_id: str) -> Path:
    return _ops.artifact_dir(workspace_root(), ree_id)


def ree_dir(ree_id: str) -> Path:
    return workspace_root() / ree_id


def metadata_path(ree_id: str) -> Path:
    return _ops.metadata_path(workspace_root(), ree_id)


def ree_manifest_path(ree_id: str) -> Path:
    return _ops.ree_manifest_path(workspace_root(), ree_id)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def read_workspace_metadata(ree_id: str) -> dict[str, Any]:
    return _ops.read_workspace_metadata(workspace_root(), ree_id)


def list_workspace_metadata(status: str | None = None) -> list[dict[str, Any]]:
    return _ops.list_workspace_metadata(workspace_root(), status=status)


def get_workspace(
    ree_id: str, seed_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    return _ops.get_workspace(workspace_root(), ree_id, seed_metadata=seed_metadata)


def list_files(ree_id: str) -> list[dict[str, Any]]:
    return _ops.list_files(workspace_root(), ree_id)


def create_workspace(payload: WorkspaceCreatePayload) -> dict[str, Any]:
    return _ops.create_workspace(
        workspace_root(),
        source_mode=payload.sourceMode,
        origin_url=payload.originUrl,
        source_type=payload.sourceType,
        name=payload.name,
    )


def patch_ree_draft(ree_id: str, payload: ReeDraftPatchPayload) -> dict[str, Any]:
    return _ops.patch_ree_draft(workspace_root(), ree_id, dict(payload.reePatch or {}))


def patch_workspace(ree_id: str, payload: WorkspacePatchPayload) -> dict[str, Any]:
    return _ops.patch_workspace(workspace_root(), ree_id, dict(payload.reePatch or {}))


def delete_workspace(ree_id: str) -> None:
    _ops.delete_workspace(workspace_root(), ree_id)


def read_file_content(ree_id: str, path: str) -> dict[str, Any]:
    return _ops.read_file_content(workspace_root(), ree_id, path)


def read_file_bytes(ree_id: str, path: str) -> bytes:
    return _ops.read_file_bytes(workspace_root(), ree_id, path)


def write_file_content(ree_id: str, path: str, content: str) -> dict[str, Any]:
    return _ops.write_file_content(workspace_root(), ree_id, path, content)


def delete_file_content(ree_id: str, path: str) -> dict[str, Any]:
    return _ops.delete_file_content(workspace_root(), ree_id, path)


def acquire_source(ree_id: str, payload: SourceAcquirePayload) -> dict[str, Any]:
    return _ops.acquire_source(
        workspace_root(), ree_id, payload.originUrl, payload.sourceType
    )


def init_source_upload(ree_id: str, payload: UploadInitPayload) -> dict[str, Any]:
    result = _ops.init_source_upload(
        workspace_root(),
        ree_id,
        payload.fileName,
        payload.size,
        payload.contentType,
    )
    result["uploadUrl"] = f"/api/v1/rees/{ree_id}/source:upload/{result['uploadToken']}"
    return result


def store_source_upload_bytes(ree_id: str, token: str, data: bytes) -> dict[str, Any]:
    return _ops.store_source_upload_bytes(workspace_root(), ree_id, token, data)


def complete_source_upload(
    ree_id: str, upload_token: str, archive_name: str
) -> dict[str, Any]:
    return _ops.complete_source_upload(
        workspace_root(), ree_id, upload_token, archive_name
    )


def remove_source(ree_id: str) -> dict[str, Any]:
    return _ops.remove_source(workspace_root(), ree_id)


def build_workspace_ree_archive(ree_id: str) -> bytes:
    return _ops.build_workspace_ree_archive(workspace_root(), ree_id)
