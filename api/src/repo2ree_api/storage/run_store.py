from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import RunLogEntry, RunOperation, RunStatus
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import Failure, HistoryReference


class StoredRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str
    ree_id: str
    operation: RunOperation
    status: RunStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested_at: str | None = None
    request: dict[str, Any]
    outputs: dict[str, Any] = Field(default_factory=dict)
    failure: Failure | None = None
    context: ExecutionContext | None = None
    history: HistoryReference | None = None
    idempotency_key: str | None = None
    request_fingerprint: str | None = None
    action: str | None = None
    action_id: str | None = None
    resumable: bool = False
    log_offset: int = 0
    cancel_sent: bool = False


class IdempotencyConflictError(Exception):
    def __init__(self, existing: StoredRun):
        self.existing = existing
        super().__init__(existing.run_id)


class RunStore(Protocol):
    def create_idempotent(self, run: StoredRun) -> tuple[StoredRun, bool]: ...

    def get(self, ree_id: str, run_id: str) -> StoredRun | None: ...

    def list_runs(self, ree_id: str) -> list[StoredRun]: ...

    def begin(self, ree_id: str, run_id: str) -> StoredRun | None: ...

    def append_log(
        self,
        ree_id: str,
        run_id: str,
        *,
        stream: str,
        level: str,
        message: str,
    ) -> RunLogEntry | None: ...

    def list_logs(
        self,
        ree_id: str,
        run_id: str,
        *,
        after_seq: int,
        limit: int | None = None,
    ) -> list[RunLogEntry]: ...

    def update_outputs(self, ree_id: str, run_id: str, outputs: dict[str, Any]) -> StoredRun | None: ...

    def request_cancel(self, ree_id: str, run_id: str) -> StoredRun | None: ...

    def is_cancel_requested(self, ree_id: str, run_id: str) -> bool: ...

    def finalize(
        self,
        ree_id: str,
        run_id: str,
        *,
        status: RunStatus,
        outputs: dict[str, Any],
        failure: Failure | None,
        context: ExecutionContext | None = None,
        history: HistoryReference | None = None,
    ) -> StoredRun | None: ...

    def record_start(self, ree_id: str, run_id: str, context: ExecutionContext) -> StoredRun | None: ...

    def record_progress(self, ree_id: str, run_id: str, log_offset: int) -> StoredRun | None: ...

    def mark_cancel_sent(self, ree_id: str, run_id: str) -> bool: ...

    def interrupt_incomplete(self) -> list[StoredRun]: ...

    def resumable_incomplete(self) -> list[StoredRun]: ...
