"""Persistence contract and private models for background runs."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import RunLogEntry, RunOperation, RunStatus
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import Failure, HistoryReference


class StoredRun(BaseModel):
    """The durable portion of one run; logs are stored separately."""

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
    # The author action this run carries out, when an author asked for it through the API
    # (a reviewer's run carries none); the run store moves it along with the run's status.
    action: str | None = None
    action_id: str | None = None
    # Whether a later API process may take the run over while its command runs on: one whose runner
    # did nothing but follow its one command to the end.
    resumable: bool = False
    # How many lines of its command's log the run has, so a later follow starts after them.
    log_offset: int = 0
    # Whether the workbench was asked to stop it: a cancel requested while it was unreachable is sent later.
    cancel_sent: bool = False


class IdempotencyConflictError(Exception):
    """An idempotency key already names a run with another payload."""

    def __init__(self, existing: StoredRun):
        self.existing = existing
        super().__init__(existing.run_id)


class RunStore(Protocol):
    """Storage operations needed by the run state machine."""

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
