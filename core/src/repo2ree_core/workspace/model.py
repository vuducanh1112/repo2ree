from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

WorkspaceStatus = Literal["draft", "ready", "sealed", "archived"]


class WorkspaceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ree_id: str = Field(alias="reeId")
    external_ref: str | None = Field(default=None, alias="externalRef")
    name: str
    status: WorkspaceStatus = "draft"
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    ree_intent: ReeIntent = Field(alias="reeIntent")
    ree_session: ReeSession = Field(alias="reeSession")
