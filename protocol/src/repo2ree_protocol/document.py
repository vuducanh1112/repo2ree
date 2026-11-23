from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.audit import ReeAudit
from repo2ree_protocol.catalog import ReeSteps
from repo2ree_protocol.command import TargetKind
from repo2ree_protocol.files import ReeFile, WorkspaceFile
from repo2ree_protocol.result import DriftedFile
from repo2ree_ree.model import Ree, ReeStatus


class WorkbenchReeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ree: Ree
    status: ReeStatus
    audit: ReeAudit
    steps: ReeSteps
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)


class ScriptState(BaseModel):
    """One of the REE's scripts: where it is and, when it is written, the digest a guarded write names."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TargetKind
    experiment_name: str | None = None
    path: str
    etag: str | None = None


class ReeStatusReport(BaseModel):
    """Where an REE stands, in one read: its steps, its evidence, its scripts, and the revision a guarded change
    names; and the run holding it, if one is."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: ReeStatus
    revision: str
    running: str | None = None
    steps: ReeSteps
    audit: ReeAudit
    scripts: list[ScriptState] = Field(default_factory=list)
    # Every file not as the last attempt left it, which the next command is refused for; None while a run holds
    # the REE, whose files are then its to change.
    drift: list[DriftedFile] | None = None
