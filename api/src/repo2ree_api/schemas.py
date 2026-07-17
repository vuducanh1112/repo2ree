"""FastAPI request payload shapes for REE / workspace routes.

REE state lives in the per-REE workbench volume (the single source of truth);
the host no longer persists workspaces, so these are pure request schemas with
no filesystem I/O — all of that happens inside the workbench via the command
envelope.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree_intent import ReeIntent

# ================================================
# Request / response payload models
# ================================================


class _StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReeCreatePayload(_StrictRequestModel):
    """Provision a new empty REE workbench.

    Source acquisition is intentionally a separate lifecycle operation through
    ``source:acquire`` or the upload-init/upload/complete sequence.
    """

    name: str | None = None
    # Image to provision the workbench from. Omitted (or blank) falls back to the
    # server default (the workbench image catalog default; see workbench_images.py).
    workbench_image: str | None = None
    # Agent to place the workbench on (from GET /api/v1/agents). Omitted/blank
    # means "any connected agent" — the single-agent path.
    agent_id: str | None = None


class ReeIntentPatchPayload(_StrictRequestModel):
    ree_intent_patch: dict[str, Any] = Field(default_factory=dict)
    expected_version: str | None = None


class ReeIntentReplacePayload(_StrictRequestModel):
    ree_intent: ReeIntent
    expected_version: str | None = None


class SourceAcquirePayload(_StrictRequestModel):
    origin_url: str
    source_type: Literal["git", "tarball", "zip"]
    # Git revision (commit, branch, or tag) to pin the fetch to. Blank/omitted
    # means the origin's default branch HEAD. Ignored for non-git sources.
    revision: str | None = None
    idempotency_key: str | None = None


class UploadInitPayload(_StrictRequestModel):
    file_name: str
    size: int = Field(ge=0)
    content_type: str


class SourceUploadCompletePayload(_StrictRequestModel):
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class WorkspaceFileContentPayload(_StrictRequestModel):
    path: str
    content: str
    if_match: str | None = None


class ReeSealPayload(_StrictRequestModel):
    include_source: bool = False
    include_runtime: bool = False
    include_results: bool = False


# ================================================
# Exceptions
# ================================================


class WorkspaceVersionConflictError(RuntimeError):
    """Raised when an intent patch is applied against a stale workspace version."""
