"""Public HTTP response and error models.

The workbench owns the rich REE document, so the API deliberately permits
additional fields on that document while pinning the stable fields automation
clients need. Run and error envelopes are strict: they are the control-plane
contract shared by every operation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal[
    "queued",
    "provisioning",
    "running",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
]
RunOperation = Literal[
    "provision",
    "build",
    "sbom",
    "crosscheck",
    "hbom",
    "activation",
    "source",
    "evaluate",
    "experiment",
]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] | list[dict[str, Any]] | None = None
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope, "description": "Invalid request or operation precondition"},
    404: {"model": ErrorEnvelope, "description": "REE, run, file, or artifact not found"},
    409: {"model": ErrorEnvelope, "description": "Version or idempotency conflict"},
    413: {"model": ErrorEnvelope, "description": "Upload exceeds the configured size limit"},
    422: {"model": ErrorEnvelope, "description": "Request validation failed"},
    502: {"model": ErrorEnvelope, "description": "Workbench returned an invalid upstream response"},
    500: {"model": ErrorEnvelope, "description": "Internal server error"},
    503: {"model": ErrorEnvelope, "description": "Workbench or runtime agent unavailable"},
    507: {"model": ErrorEnvelope, "description": "Upload staging capacity exhausted"},
}


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    ree_id: str
    operation: RunOperation
    status: RunStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)


class RunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[RunSummary]
    next_cursor: str | None = None


class RunLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    ts: str
    stream: Literal["stdout", "stderr", "system"]
    level: Literal["debug", "info", "warn", "error"]
    message: str


class RunLogPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[RunLogEntry]
    next_cursor: str | None = None
    has_more: bool
    run_status: RunStatus


class RunObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunSummary
    entries: list[RunLogEntry]
    next_cursor: str | None = None
    changed: bool


class CancelRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RunStatus


class ReeDocument(BaseModel):
    """The stable identity/version fields plus the workbench-owned document."""

    model_config = ConfigDict(extra="allow")

    ree_id: str
    name: str
    status: str
    created_at: str
    updated_at: str


class ReeSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    ree_id: str
    name: str
    status: str
    created_at: str
    updated_at: str


class ReeList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReeSummary]
    next_cursor: str | None = None


class ReeState(BaseModel):
    """Compact control-plane observation without inline workspace content."""

    model_config = ConfigDict(extra="allow")

    ree_id: str
    name: str
    status: str
    updated_at: str
    workbench: dict[str, Any]
    ree_intent: dict[str, Any] = Field(default_factory=dict)
    ree_session: dict[str, Any] = Field(default_factory=dict)
    consistency: dict[str, Any] = Field(default_factory=dict)
    files: list[dict[str, Any]] = Field(default_factory=list)
    active_runs: list[RunSummary] = Field(default_factory=list)


class DeleteReeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_at: str
    state: Literal["deleted"]


class UploadInitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_token: str
    upload_url: str
    expires_at: str


class UploadStoredResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_token: str
    stored_at: str


class FileMutationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    updated_at: str | None = None
    deleted_at: str | None = None
    etag: str | None = None


class ReprovisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["reprovisioned"]
    ree_id: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["online"]
    message: str
