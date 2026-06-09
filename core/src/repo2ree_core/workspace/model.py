from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

WorkspaceStatus = Literal["draft", "ready", "sealed", "archived"]
SourceMode = Literal["download", "upload"]


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    mode: SourceMode
    origin_url: str | None = Field(default=None, alias="originUrl")
    source_type: str | None = Field(default=None, alias="sourceType")
    archive_name: str | None = Field(default=None, alias="archiveName")
    upload_token: str | None = Field(default=None, alias="uploadToken")
    acquired_at: str | None = Field(default=None, alias="acquiredAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    snapshot_archive: str | None = Field(default=None, alias="snapshotArchive")
    snapshot_captured_at: str | None = Field(default=None, alias="snapshotCapturedAt")


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
    source: SourceMetadata | None = None
