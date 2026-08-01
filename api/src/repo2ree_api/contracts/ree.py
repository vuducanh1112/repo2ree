"""Public REE response models.

The workbench owns the rich REE document; the typed fields here reuse the core
models the workbench produces it from, so the contract cannot drift from the
producers. The contract is total: an unknown key coming out of the workbench is
an error, not a passthrough.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts.runs import RunSummary
from repo2ree_api.ree_index import ReeIndexEntry
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.consistency import AuthorReceiptSet, ConsistencyReport
from repo2ree_core.evidence.step_graph import ReeStepState
from repo2ree_core.persistence.workspace.inventory import ReeFile, WorkspaceFile
from repo2ree_core.source_repo.metadata import SourceRepoMetadata


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
    ree_state: ReeLifecycleState = Field(default_factory=ReeLifecycleState)
    files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)
    # Read-only projection of the would-be manifest; its source of truth is
    # the sealed manifest, so it stays a passthrough here.
    draft_manifest: dict[str, Any] = Field(default_factory=dict)
    source_repo: SourceRepoMetadata | None = None
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)
    author_receipts: AuthorReceiptSet = Field(default_factory=AuthorReceiptSet)
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


class ReeIndexList(BaseModel):
    """A page of the REE index — sealed REEs and where they were deposited.

    The item type is the stored entry itself, for the same reason ``ReeDocument``
    reuses the core models: a separate wire shape could drift from what is
    actually on disk, and here that drift would be published to peers.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ReeIndexEntry]
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
    ree_state: ReeLifecycleState = Field(default_factory=ReeLifecycleState)
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)
    author_receipts: AuthorReceiptSet = Field(default_factory=AuthorReceiptSet)
    ree_steps: list[ReeStepState] = Field(default_factory=list)
    files: list[WorkspaceFile] = Field(default_factory=list)
    # REE-owned files (artifacts/, overlay/, …) alongside the materialized
    # workspace tree: produced evidence like the SBOM lives only here, so a
    # state observation without them cannot see it at all.
    ree_files: list[ReeFile] = Field(default_factory=list)
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
