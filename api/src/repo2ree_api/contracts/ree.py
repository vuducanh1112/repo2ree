"""Public REE response models over the portable aggregate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts.runs import RunSummary
from repo2ree_api.ree_index import ReeIndexEntry
from repo2ree_core.domain.ree.audit import ReeAudit
from repo2ree_core.domain.ree.model import Ree, ReeStatus
from repo2ree_core.operations.read_models.files import ReeFile, WorkspaceFile


class ReeDocument(BaseModel):
    """The portable aggregate with live workbench file projections."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    ree: Ree
    status: ReeStatus
    audit: ReeAudit
    workbench_image: str | None = None
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)


class ReeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ree_id: str
    name: str
    status: ReeStatus
    workbench_image: str | None = None


class ReeList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReeSummary]
    next_cursor: str | None = None


class ReeIndexList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReeIndexEntry]
    next_cursor: str | None = None


class WorkbenchStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    agent_id: str | None = None
    image: str | None = None


class ReeState(BaseModel):
    """Compact control-plane observation without inline file contents."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    ree: Ree
    status: ReeStatus
    audit: ReeAudit
    workbench: WorkbenchStatus
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)
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
