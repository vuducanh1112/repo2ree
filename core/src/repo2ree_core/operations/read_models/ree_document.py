"""API-facing projection of a portable REE and its live file views."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree.assessment import assess
from repo2ree_core.domain.ree.model import Ree, ReeAssessment, ReeStatus, ree_status
from repo2ree_core.operations.read_models.files import (
    ReeFile,
    WorkspaceFile,
    list_ree_files,
    list_workspace_files,
)
from repo2ree_core.persistence.repository import directory_for, layout_for, load_ree


class ReeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ree_id: str
    ree: Ree
    status: ReeStatus
    assessment: ReeAssessment
    workspace_files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)


def get_ree_document(storage_root: Path, ree_id: str, *, include_content: bool = True) -> ReeDocument:
    layout = layout_for(storage_root, ree_id)
    directory = directory_for(storage_root, ree_id)
    if not directory.record_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    ree = load_ree(layout, directory)
    return ReeDocument(
        ree_id=ree_id,
        ree=ree,
        status=ree_status(ree),
        assessment=assess(ree),
        workspace_files=list_workspace_files(storage_root, ree_id, include_content=include_content),
        ree_files=list_ree_files(storage_root, ree_id, include_content=include_content),
    )
