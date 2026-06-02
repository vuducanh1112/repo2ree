"""FastAPI request payload shapes for REE / workspace routes.

REE state lives in the per-REE workbench volume (the single source of truth);
the host no longer persists workspaces, so these are pure request schemas with
no filesystem I/O — all of that happens inside the workbench via the command
envelope.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ================================================
# Request / response payload models
# ================================================


class WorkspaceCreatePayload(BaseModel):
    sourceMode: Literal["url", "upload"]
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


# ================================================
# Exceptions
# ================================================


class WorkspaceVersionConflictError(RuntimeError):
    """Raised when a draft patch is applied against a stale workspace version."""
