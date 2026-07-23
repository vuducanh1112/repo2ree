"""Public HTTP response and error models.

The workbench owns the rich REE document, so the API deliberately permits
additional fields on that document while pinning the stable fields automation
clients need. Run and error envelopes are strict: they are the control-plane
contract shared by every operation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.receipts import ConsistencyReport
from repo2ree_core.ree_steps import ReeStepState
from repo2ree_core.source_repo.metadata import SourceRepoMetadata
from repo2ree_core.workspace.inventory import ReeFile, WorkspaceFile
from repo2ree_protocol.result import Failure

# The run vocabulary. It is part of the wire contract (it lands in the OpenAPI
# schema through RunSummary), so it is declared here once and imported by the
# registry and the run routes rather than re-spelled next to each of them.
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
    # Set on a failed run: the typed reason the run did not succeed, so a client
    # can pivot off `status == "failed"` without parsing the log stream. Absent
    # for succeeded/canceled runs, and (best-effort) for a failure that predates
    # this contract or arises outside a single ActionResult.
    failure: Failure | None = None


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
    """The workbench-owned REE document, typed in full.

    The typed fields reuse the core models the workbench produces the document
    from, so the contract cannot drift from the producers. The contract is
    total: an unknown key coming out of the workbench is an error, not a
    passthrough.
    """

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    external_ref: str | None = None
    # Set by the manager (which owns the registry) on direct fetches; absent
    # from document responses embedded in other operations.
    workbench_image: str | None = None
    ree_intent: ReeIntent = Field(default_factory=ReeIntent)
    ree_session: ReeSession = Field(default_factory=ReeSession)
    files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)
    # Read-only projection of the would-be manifest; its source of truth is
    # the sealed manifest, so it stays a passthrough here.
    draft_manifest: dict[str, Any] = Field(default_factory=dict)
    source_repo: SourceRepoMetadata | None = None
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)
    ree_steps: list[ReeStepState] = Field(default_factory=list)


class ReeSummary(BaseModel):
    # A projection: routes feed this the full workbench sidecar and validation
    # drops everything beyond the summary fields, so the wire matches the
    # contract exactly.
    model_config = ConfigDict(extra="ignore")

    ree_id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    external_ref: str | None = None


class ReeList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReeSummary]
    next_cursor: str | None = None


class WorkbenchStatus(BaseModel):
    """Whether (and where) a live workbench backs the REE."""

    model_config = ConfigDict(extra="forbid")

    status: str
    agent_id: str | None = None
    image: str | None = None


class ReeState(BaseModel):
    """Compact control-plane observation without inline workspace content."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    name: str
    status: str
    updated_at: str
    workbench: WorkbenchStatus
    ree_intent: ReeIntent = Field(default_factory=ReeIntent)
    ree_session: ReeSession = Field(default_factory=ReeSession)
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)
    ree_steps: list[ReeStepState] = Field(default_factory=list)
    files: list[WorkspaceFile] = Field(default_factory=list)
    source_repo: SourceRepoMetadata | None = None
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
    model_config = ConfigDict(extra="forbid")

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
