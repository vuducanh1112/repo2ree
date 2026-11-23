from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, DriftedFile, Failure, OperationStatus

SELECTION_VERSION = 2


class OperationRecord(BaseModel):
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
    step_evidence_before: dict[str, str] | None = None
    drift_found: list[DriftedFile] = Field(default_factory=list)
    drift_recorded: str | None = None
    drift_after: list[DriftedFile] = Field(default_factory=list)
    step_evidence_after: dict[str, str] | None = None
    phases: list[Literal["pending", "executing", "completed", "captured", "capture_failed"]] = Field(
        default_factory=list
    )


class OperationHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[OperationRecord] = Field(default_factory=list)


class CompletedOperation(OperationRecord):
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
