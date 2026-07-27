"""The run vocabulary and the response models built on it.

``RunStatus`` / ``RunOperation`` are part of the wire contract (they land in the
OpenAPI schema through ``RunSummary``), so they are declared here once and
imported by the registry and the run routes rather than re-spelled next to each.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.result import Failure

RunStatus = Literal[
    "queued",
    "provisioning",
    "running",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
]
RunOperation = Literal[
    "provision",
    "ree-load",
    "build",
    "sbom",
    "crosscheck",
    "hbom",
    "activation",
    "source",
    "evaluate",
    "experiment",
]


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
    # Set on a failed run: the typed reason the run did not succeed, so a client
    # can pivot off `status == "failed"` without parsing the log stream. Absent
    # for succeeded/canceled runs, and (best-effort) for a failure that predates
    # this contract or arises outside a single ActionResult.
    failure: Failure | None = None


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
