from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _backfill_intent_identity(self) -> WorkspaceMetadata:
        # The sidecar's identity fields (name, external_ref) are always derived
        # from the intent at every write site, but a sidecar can exist before
        # the author fills the intent in — fall back to the identity fields so
        # the intent is never blanker than the workspace it describes.
        if not self.ree_intent.name:
            self.ree_intent.name = self.name
        if not self.ree_intent.origin_url and self.external_ref:
            self.ree_intent.origin_url = self.external_ref
        return self
