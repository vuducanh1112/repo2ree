from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.execution import ExecutionContext

ActionStatus = Literal["succeeded", "failed", "canceled"]
OperationStatus = ActionStatus | Literal["interrupted"]

FailureCategory = Literal[
    "validation",
    "precondition",
    "conflict",
    "execution",
    "timeout",
    "unavailable",
    "internal",
]

FailureOrigin = Literal["api", "supervisor", "workbench", "executor", "core"]


class Failure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    message: str
    retryable: bool = False
    origin: FailureOrigin
    details: dict[str, Any] | None = None


ReePart = Literal["overlay", "workspace", "records", "history"]


class DriftedFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    part: ReePart


class HistoryReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    selection_version: int
    attempt_id: str
    scope: str
    capture_status: Literal["pending", "captured", "failed"]
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    operation_status: OperationStatus | Literal["not_started", "unknown"]
    operation_failure: Failure | None = None
    changed: bool | None = None
    record_digest: str | None = None
    drift_after: list[DriftedFile] = Field(default_factory=list)


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ActionStatus
    exit_code: int = 0
    outputs: dict[str, Any] = {}
    failure: Failure | None = None
    context: ExecutionContext | None = None
    history: HistoryReference | None = None

    @model_validator(mode="after")
    def _enforce_status_invariants(self) -> Self:
        if self.context is not None and self.history is not None and self.context.attempt_id != self.history.attempt_id:
            raise ValueError("History reference belongs to another execution attempt")
        if self.status == "succeeded":
            if self.exit_code != 0:
                raise ValueError("a succeeded ActionResult must have exit_code 0")
            if self.failure is not None:
                raise ValueError("a succeeded ActionResult must not carry a failure")
        elif self.status == "failed":
            if self.exit_code == 0:
                raise ValueError("a failed ActionResult must have a nonzero exit_code")
            if self.failure is None:
                raise ValueError("a failed ActionResult must carry a failure")
        else:
            if self.failure is not None:
                raise ValueError("a canceled ActionResult must not carry a failure")
        return self

    @classmethod
    def failed(
        cls,
        category: FailureCategory,
        message: str,
        *,
        origin: FailureOrigin = "core",
        exit_code: int = 1,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> ActionResult:
        return cls(
            status="failed",
            exit_code=exit_code or 1,
            outputs=outputs or {},
            failure=Failure(
                category=category,
                message=message,
                retryable=retryable,
                origin=origin,
                details=details,
            ),
        )
