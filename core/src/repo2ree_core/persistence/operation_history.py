"""Persisted invocation records and read access, independent of command dispatch."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import SELECTION_VERSION, GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.tooling import find_tool
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, ActionStatus, Failure


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


def history_scopes(layout: ReeLayout) -> list[ReeLayout]:
    scopes = [layout]
    if layout.reviews.is_dir():
        scopes.extend(
            ReviewLayout(root=path)
            for path in sorted(layout.reviews.iterdir())
            if path.is_dir() and not path.is_symlink()
        )
    return scopes


def read_operation_history(layout: ReeLayout) -> OperationHistory:
    records = []
    for scope in history_scopes(layout):
        scoped: dict[str, OperationRecord] = {}
        directory = scope.git_dir / "repo2ree" / "operations"
        if scope.git_dir.is_symlink():
            raise HistoryCaptureError("REE history requires a local .git directory")
        if scope.git_dir.is_dir():
            executable = find_tool("git")
            if executable is None:
                raise HistoryCaptureError("Git is required to read REE history")
            published: set[str] = set()
            for commit, document in GitHistory(scope, executable).completed_operations():
                completed = CompletedOperation.model_validate(document)
                record = OperationRecord.model_validate(completed.model_dump())
                record.after_snapshot_id = commit
                record.capture_status = "captured"
                # Newest published entry wins over stale pending/legacy files.
                if record.attempt_id in published:
                    previous = scoped[record.attempt_id]
                    if previous.model_dump(exclude={"after_snapshot_id"}) != record.model_dump(
                        exclude={"after_snapshot_id"}
                    ):
                        raise HistoryCaptureError(f"Conflicting journal identity: {record.attempt_id}")
                if record.attempt_id not in published:
                    scoped[record.attempt_id] = record
                    published.add(record.attempt_id)
        for path in sorted(directory.glob("*.json")):
            if path.stem in scoped:
                continue
            try:
                document_text = path.read_text()
            except FileNotFoundError:
                # Concurrent publication may have reclaimed this pending file.
                continue
            record = OperationRecord.model_validate_json(document_text)
            if record.attempt_id not in scoped:
                scoped[record.attempt_id] = record
        for record in scoped.values():
            # Scope comes from storage, never from an imported record's claim.
            record.scope = scope.root.relative_to(layout.root).as_posix()
            records.append(record)
    # Legacy records have no known attempt order; retain them after sequenced
    # records without fabricating chronology from their UUIDs or file mtimes.
    records.sort(
        key=lambda record: (record.sequence is not None, record.sequence or 0, record.attempt_id), reverse=True
    )
    return OperationHistory(operations=records)


def next_operation_sequence(layout: ReeLayout) -> int:
    """Allocate under the author history lock, shared across review scopes."""
    path = layout.git_dir / "repo2ree" / "sequence.json"
    if path.exists():
        previous = int(json.loads(path.read_text())["sequence"])
    else:
        previous = max((record.sequence or 0 for record in read_operation_history(layout).operations), default=0)
    sequence = previous + 1
    write_json_atomic(path, {"sequence": sequence})
    return sequence
