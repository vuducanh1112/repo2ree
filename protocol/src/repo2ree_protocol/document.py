from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.audit import ReeAudit
from repo2ree_protocol.catalog import ReeSteps
from repo2ree_protocol.files import ReeFile, WorkspaceFile
from repo2ree_ree.model import Ree, ReeStatus


class WorkbenchReeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ree: Ree
    status: ReeStatus
    audit: ReeAudit
    steps: ReeSteps
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)
