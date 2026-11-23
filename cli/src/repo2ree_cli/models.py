from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.review import ReviewRecord


class _Outputs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Initialized(_Outputs):
    root: str
    state: Literal["initialised", "already_initialised"]
    snapshot_id: str


class ScriptWritten(_Outputs):
    path: str
    rule: str
    candidate_id: str


class ScriptEdited(_Outputs):
    path: str
    changed: bool


class Waited(_Outputs):
    held_by: str | None = None


class CancelRequested(_Outputs):
    run_id: str


class StepRun(_Outputs):
    words: list[str]
    run_id: str
    status: ActionStatus


class ReviewRun(_Outputs):
    review_id: str
    steps: list[StepRun] = Field(default_factory=list)
    review: ReviewRecord | None = None
