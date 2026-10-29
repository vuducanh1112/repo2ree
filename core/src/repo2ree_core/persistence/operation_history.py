"""Persisted invocation records and read access, independent of command dispatch."""

from __future__ import annotations

import json

from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_protocol.history import CompletedOperation, OperationHistory, OperationRecord
from repo2ree_protocol.tools import find_tool


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
