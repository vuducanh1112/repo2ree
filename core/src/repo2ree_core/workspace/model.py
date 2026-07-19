from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

WorkspaceStatus = Literal["draft", "ready", "sealed", "archived"]


class WorkspaceMetadata(BaseModel):
    """The full schema of the ``.workspace.json`` sidecar."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    external_ref: str | None = None
    name: str
    status: WorkspaceStatus = "draft"
    created_at: str
    updated_at: str
    ree_intent: ReeIntent = Field(default_factory=ReeIntent)
    ree_session: ReeSession = Field(default_factory=ReeSession)
