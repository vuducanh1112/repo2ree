from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.command import OperationName
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import Failure, HistoryReference

RunStatus = Literal[
    "queued",
    "provisioning",
    "running",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
]
RunOperation = OperationName

OPERATIONS_EXTENSION = "x-operations"


def runs(*operations: OperationName) -> dict[str, Any]:
    return {OPERATIONS_EXTENSION: list(operations)}


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    ree_id: str
    operation: RunOperation
    status: RunStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    failure: Failure | None = None
    context: ExecutionContext | None = None
    history: HistoryReference | None = None


class RunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[RunSummary]
    next_cursor: str | None = None


class RunLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    ts: str
    stream: Literal["stdout", "stderr", "system"]
    level: Literal["debug", "info", "warn", "error"]
    message: str


class RunLogPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[RunLogEntry]
    next_cursor: str | None = None
    has_more: bool
    run_status: RunStatus


class RunObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunSummary
    entries: list[RunLogEntry]
    next_cursor: str | None = None
    changed: bool


class CancelRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RunStatus
