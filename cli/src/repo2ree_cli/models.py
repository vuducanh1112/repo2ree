"""The outputs of what ``ree`` does beyond one command: several commands in a row, or nothing run at all."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.review import ReviewRecord


class _Outputs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Initialized(_Outputs):
    """``init``: the REE and the snapshot its first version is."""

    root: str
    state: Literal["initialised", "already_initialised"]
    snapshot_id: str


class ScriptWritten(_Outputs):
    """``infer --write``: the script written, and the proposal it is."""

    path: str
    rule: str
    candidate_id: str


class ScriptEdited(_Outputs):
    """``edit``: the script, and whether the edit changed it."""

    path: str
    changed: bool


class Waited(_Outputs):
    """``wait``: the run that held the REE when the wait began, if one did."""

    held_by: str | None = None


class CancelRequested(_Outputs):
    """``cancel``: the run asked to stop."""

    run_id: str


class StepRun(_Outputs):
    """One command a composite ran: its words, its run, and how it ended."""

    words: list[str]
    run_id: str
    status: ActionStatus


class ReviewRun(_Outputs):
    """``review all``: the review, each step it ran, and the review as it stands after them."""

    review_id: str
    steps: list[StepRun] = Field(default_factory=list)
    review: ReviewRecord | None = None
