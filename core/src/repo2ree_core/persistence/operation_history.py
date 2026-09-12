"""Persisted invocation records and read access, independent of command dispatch."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import SELECTION_VERSION
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_protocol.result import ActionStatus, Failure


class OperationRecord(BaseModel):
    """One invocation, including no-ops and attempts left pending by process death."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    selection_version: int = SELECTION_VERSION
    attempt_id: str
    run_id: str
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


class OperationHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: list[OperationRecord] = Field(default_factory=list)


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
        directory = scope.git_dir / "repo2ree" / "operations"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            record = OperationRecord.model_validate_json(path.read_text())
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
