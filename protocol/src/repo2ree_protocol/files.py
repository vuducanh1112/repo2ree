from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

WorkspaceFileKind = Literal["source", "generated"]


class WorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: WorkspaceFileKind
    size: int
    content: str | None = None


class ReeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    kind: Literal["ree"] = "ree"
    tag: str
    size: int
    content: str | None = None
