"""Versioned transport metadata; domain file selection belongs to capture."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.persistence.lfs import LfsPointer


class ScopeExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: str
    head: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    lfs_objects: tuple[LfsPointer, ...] = ()


class RepositoryExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[2] = 2
    selection_version: Literal[2] = 2
    scopes: tuple[ScopeExport, ...]
    payload_completeness: Literal["selected_commits"] = "selected_commits"
    limitations: tuple[str, ...] = (
        "Historical LFS pointers may refer to payloads absent from this export.",
        "Pending attempts are unresolved; completed operations are read from Git.",
        "Generated workspace and upstream trees are not captured.",
    )
