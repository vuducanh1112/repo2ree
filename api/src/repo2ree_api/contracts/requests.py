"""Request payload shapes for every route.

REE state lives in the per-REE workbench volume (the single source of truth);
the host no longer persists workspaces, so these are pure request schemas with
no filesystem I/O — all of that happens inside the workbench via the command
envelope.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree.model import ReeDefinition


class StrictRequestModel(BaseModel):
    """Base for request bodies: an unknown field is a client error, not ignored.

    Declared here with the rest of the control-plane contract so every route's
    payload inherits the same strictness instead of re-spelling the config.
    """

    model_config = ConfigDict(extra="forbid")


class CreateRunPayload(StrictRequestModel):
    """The body every "start a run" route accepts.

    Routes that need nothing else subclass it as-is; the two that take
    parameters (sbom, evaluate) add their fields. Subclassing rather than
    sharing one model keeps each route's schema named after its operation.
    """

    idempotency_key: str | None = None


class ReeCreatePayload(StrictRequestModel):
    """Provision a new empty REE workbench.

    Source acquisition is intentionally a separate lifecycle operation through
    ``source:acquire`` or the upload-init/upload/complete sequence.
    """

    name: str | None = None
    # Image to provision the workbench from. Omitted (or blank) falls back to the
    # server default (the workbench image catalog default; see settings.py).
    workbench_image: str | None = None
    # Agent to place the workbench on (from GET /api/v1/agents). Omitted/blank
    # means "any connected agent" — the single-agent path.
    agent_id: str | None = None


class ReeDefinitionPatchPayload(StrictRequestModel):
    """Merge top-level fields into the current portable REE definition."""

    definition_patch: dict[str, object] = Field(default_factory=dict)
    expected_version: str | None = None


class ReeDefinitionReplacePayload(StrictRequestModel):
    definition: ReeDefinition
    expected_version: str | None = None


class SourceAcquirePayload(StrictRequestModel):
    origin_url: str
    source_type: Literal["git", "tarball", "zip"]
    # Git revision (commit, branch, or tag) to pin the fetch to. Blank/omitted
    # means the origin's default branch HEAD. Ignored for non-git sources.
    revision: str | None = None
    idempotency_key: str | None = None


class UploadInitPayload(StrictRequestModel):
    file_name: str
    size: int = Field(ge=0)
    content_type: str


class SourceUploadCompletePayload(StrictRequestModel):
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class ReeBundleLoadPayload(StrictRequestModel):
    """Load a staged REE bundle into this (freshly provisioned) REE."""

    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class WorkspaceFileContentPayload(StrictRequestModel):
    path: str
    content: str
    if_match: str | None = None


class ReeSealPayload(StrictRequestModel):
    include_source: bool = False
    include_runtime: bool = False
    include_results: bool = False
