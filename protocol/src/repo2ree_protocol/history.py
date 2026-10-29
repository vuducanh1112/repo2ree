from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, ActionStatus, Failure

SELECTION_VERSION = 2


class OperationRecord(BaseModel):
    """One invocation, including no-ops and attempts left pending by process death."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    selection_version: int = SELECTION_VERSION
    attempt_id: str
    run_id: str
    context: ExecutionContext | None = None
    sequence: int | None = None
    command: dict[str, Any]
    scope: str
    author_seal_digest: str | None = None
    capture_status: Literal["pending", "captured", "failed"] = "pending"
    operation_status: ActionStatus | Literal["not_started", "unknown"] = "not_started"
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    operation_failure: Failure | None = None
    capture_error: str | None = None
    result: ActionResult | None = None
    changed: bool | None = None
    # Evidence standing of every author step (``audit``) around the handler, so
    # the history shows which attempt made which receipt current or stale.
    # None for review scopes, legacy records, and REEs that could not be audited.
    step_evidence_before: dict[str, str] | None = None
    step_evidence_after: dict[str, str] | None = None
    # Each phase the attempt entered, appended and written before the next begins:
    # pending, executing, completed, then captured or capture_failed. The record of
    # what happened in order, rather than a final state to infer it from.
    phases: list[Literal["pending", "executing", "completed", "captured", "capture_failed"]] = Field(
        default_factory=list
    )


class OperationHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[OperationRecord] = Field(default_factory=list)


class CompletedOperation(OperationRecord):
    """The record bound to an operation commit; its own ID is derived on read."""

    context: ExecutionContext
    result: ActionResult
    before_snapshot_id: str
    after_snapshot_id: None = None
    operation_status: ActionStatus
    capture_status: Literal["captured"] = "captured"

    @model_validator(mode="after")
    def consistent_outcome(self) -> CompletedOperation:
        if self.attempt_id != self.context.attempt_id or self.result.context != self.context:
            raise ValueError("Operation identity differs from its result")
        if self.result.history is not None:
            raise ValueError("A completed record cannot reference its own commit")
        if self.result.status != self.operation_status or self.result.failure != self.operation_failure:
            raise ValueError("Operation outcome differs from its result")
        return self
