from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, DriftedFile, Failure, OperationStatus

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
    operation_status: OperationStatus | Literal["not_started", "unknown"] = "not_started"
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
    # What had drifted when the attempt began: every file not as the last attempt left it. An attempt that found
    # drift records the one script edit it names in ``drift_recorded``, or is refused.
    drift_found: list[DriftedFile] = Field(default_factory=list)
    drift_recorded: str | None = None
    # What had changed beside the attempt once its handler returned: every file of the REE no longer as the attempt
    # found it. The handler ran on a stage, so none of it reached the attempt or its commit; the next command finds it.
    drift_after: list[DriftedFile] = Field(default_factory=list)
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
    operation_status: OperationStatus
    capture_status: Literal["captured"] = "captured"

    @model_validator(mode="after")
    def consistent_outcome(self) -> CompletedOperation:
        if self.attempt_id != self.context.attempt_id or self.result.context != self.context:
            raise ValueError("Operation identity differs from its result")
        if self.result.history is not None:
            raise ValueError("A completed record cannot reference its own commit")
        reported = "failed" if self.operation_status == "interrupted" else self.operation_status
        if self.result.status != reported or self.result.failure != self.operation_failure:
            raise ValueError("Operation outcome differs from its result")
        return self
