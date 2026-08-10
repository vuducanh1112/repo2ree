"""Single-process JSON persistence for background runs.

Each generated run id owns a directory containing an atomically replaced
``state.json`` and an append-only ``logs.jsonl``. Complete read-modify-write
transactions are serialized across threads. This backend deliberately does not
coordinate multiple API processes.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from repo2ree_api.contracts import RunLogEntry, RunStatus
from repo2ree_api.storage.run_store import IdempotencyConflictError, StoredRun
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.result import Failure

_ACTIVE_STATUSES = frozenset({"running", "queued", "provisioning", "canceling"})
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "canceled"})


class JsonRunStore:
    """Thread-safe JSON run store for one API process."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = RLock()
        self._runs: dict[tuple[str, str], Path] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._next_log_seq: dict[tuple[str, str], int] = {}
        self._load_indexes()

    def create_idempotent(self, run: StoredRun) -> tuple[StoredRun, bool]:
        with self._lock:
            if run.idempotency_key:
                slot = (run.ree_id, run.operation, run.idempotency_key)
                existing_ref = self._idempotency.get(slot)
                if existing_ref is not None:
                    existing = self._read_state_unlocked(self._runs[existing_ref])
                    if existing.request_fingerprint != run.request_fingerprint:
                        raise IdempotencyConflictError(existing)
                    return existing, False

            run_dir = self._root / run.run_id
            if run_dir.exists():
                raise FileExistsError(f"run directory already exists: {run.run_id}")
            run_dir.mkdir(parents=True)
            self._write_state_unlocked(run_dir / "state.json", run)
            key = (run.ree_id, run.run_id)
            self._runs[key] = run_dir
            self._next_log_seq[key] = 1
            if run.idempotency_key:
                self._idempotency[(run.ree_id, run.operation, run.idempotency_key)] = key
            return run.model_copy(deep=True), True

    def get(self, ree_id: str, run_id: str) -> StoredRun | None:
        with self._lock:
            run_dir = self._runs.get((ree_id, run_id))
            return None if run_dir is None else self._read_state_unlocked(run_dir)

    def list_runs(self, ree_id: str) -> list[StoredRun]:
        with self._lock:
            runs = [
                self._read_state_unlocked(run_dir)
                for (stored_ree_id, _run_id), run_dir in self._runs.items()
                if stored_ree_id == ree_id
            ]
        runs.sort(key=lambda run: (run.created_at, run.run_id), reverse=True)
        return runs

    def begin(self, ree_id: str, run_id: str) -> StoredRun | None:
        with self._lock:
            current = self._get_unlocked(ree_id, run_id)
            if current is None:
                return None
            status: RunStatus = current.status
            if status == "queued":
                status = "provisioning" if current.operation == "provision" else "running"
            updated = current.model_copy(update={"started_at": utc_now(), "status": status})
            self._write_for_run_unlocked(updated)
            return updated

    def append_log(
        self,
        ree_id: str,
        run_id: str,
        *,
        stream: str,
        level: str,
        message: str,
    ) -> RunLogEntry | None:
        with self._lock:
            key = (ree_id, run_id)
            run_dir = self._runs.get(key)
            if run_dir is None:
                return None
            entry = RunLogEntry.model_validate(
                {
                    "seq": self._next_log_seq[key],
                    "ts": utc_now(),
                    "stream": stream,
                    "level": level,
                    "message": message,
                }
            )
            with (run_dir / "logs.jsonl").open("a", encoding="utf-8") as output:
                output.write(entry.model_dump_json())
                output.write("\n")
                output.flush()
            self._next_log_seq[key] = entry.seq + 1
            return entry

    def list_logs(
        self,
        ree_id: str,
        run_id: str,
        *,
        after_seq: int,
        limit: int | None = None,
    ) -> list[RunLogEntry]:
        with self._lock:
            run_dir = self._runs.get((ree_id, run_id))
            if run_dir is None:
                return []
            entries = [entry for entry in self._read_logs_unlocked(run_dir) if entry.seq > after_seq]
            return entries if limit is None else entries[:limit]

    def update_outputs(self, ree_id: str, run_id: str, outputs: dict[str, Any]) -> StoredRun | None:
        with self._lock:
            current = self._get_unlocked(ree_id, run_id)
            if current is None:
                return None
            updated = current.model_copy(update={"outputs": dict(outputs)})
            self._write_for_run_unlocked(updated)
            return updated

    def request_cancel(self, ree_id: str, run_id: str) -> StoredRun | None:
        with self._lock:
            current = self._get_unlocked(ree_id, run_id)
            if current is None:
                return None
            changes: dict[str, Any] = {}
            if current.cancel_requested_at is None:
                changes["cancel_requested_at"] = utc_now()
            if current.status in _ACTIVE_STATUSES:
                changes["status"] = "canceling"
            if not changes:
                return current
            updated = current.model_copy(update=changes)
            self._write_for_run_unlocked(updated)
            return updated

    def is_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._lock:
            current = self._get_unlocked(ree_id, run_id)
            return current is not None and current.cancel_requested_at is not None

    def finalize(
        self,
        ree_id: str,
        run_id: str,
        *,
        status: RunStatus,
        outputs: dict[str, Any],
        failure: Failure | None,
    ) -> StoredRun | None:
        with self._lock:
            current = self._get_unlocked(ree_id, run_id)
            if current is None:
                return None
            if current.cancel_requested_at is not None and status not in {"failed", "succeeded"}:
                status = "canceled"
                failure = None
            updated = current.model_copy(
                update={
                    "status": status,
                    "outputs": dict(outputs),
                    "failure": failure,
                    "finished_at": utc_now() if status in _TERMINAL_STATUSES else None,
                }
            )
            self._write_for_run_unlocked(updated)
            return updated

    def interrupt_incomplete(self) -> list[StoredRun]:
        interrupted: list[StoredRun] = []
        failure = Failure(
            category="internal",
            message="API process stopped before the run completed",
            retryable=True,
            origin="api",
            details={"code": "run_interrupted"},
        )
        with self._lock:
            for key, run_dir in self._runs.items():
                current = self._read_state_unlocked(run_dir)
                if current.status not in _ACTIVE_STATUSES:
                    continue
                updated = current.model_copy(update={"status": "failed", "failure": failure, "finished_at": utc_now()})
                self._write_state_unlocked(run_dir / "state.json", updated)
                interrupted.append(updated)
                self._next_log_seq[key] = self._next_sequence_unlocked(run_dir)
        return interrupted

    def _load_indexes(self) -> None:
        with self._lock:
            if not self._root.exists():
                return
            for state_path in sorted(self._root.glob("*/state.json")):
                run = self._read_state_unlocked(state_path.parent)
                key = (run.ree_id, run.run_id)
                if key in self._runs:
                    raise ValueError(f"duplicate persisted run: {run.ree_id}/{run.run_id}")
                self._runs[key] = state_path.parent
                self._next_log_seq[key] = self._next_sequence_unlocked(state_path.parent)
                if run.idempotency_key:
                    slot = (run.ree_id, run.operation, run.idempotency_key)
                    if slot in self._idempotency:
                        raise ValueError(f"duplicate persisted idempotency key: {slot}")
                    self._idempotency[slot] = key

    def _get_unlocked(self, ree_id: str, run_id: str) -> StoredRun | None:
        run_dir = self._runs.get((ree_id, run_id))
        return None if run_dir is None else self._read_state_unlocked(run_dir)

    def _write_for_run_unlocked(self, run: StoredRun) -> None:
        run_dir = self._runs[(run.ree_id, run.run_id)]
        self._write_state_unlocked(run_dir / "state.json", run)

    def _read_state_unlocked(self, path: Path) -> StoredRun:
        state_path = path if path.name == "state.json" else path / "state.json"
        return StoredRun.model_validate_json(state_path.read_text(encoding="utf-8"))

    def _write_state_unlocked(self, path: Path, run: StoredRun) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="state.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(run.model_dump_json(indent=2))
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            Path(temporary).replace(path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def _read_logs_unlocked(self, run_dir: Path) -> list[RunLogEntry]:
        path = run_dir / "logs.jsonl"
        if not path.exists():
            return []
        lines = path.read_bytes().splitlines(keepends=True)
        entries: list[RunLogEntry] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(RunLogEntry.model_validate_json(stripped))
            except ValueError:
                if index != len(lines) - 1:
                    raise
                # A process can stop after writing only part of its final JSON
                # object. Remove that fragment so the next append starts on a
                # clean line and sequence recovery remains durable.
                path.write_bytes(b"".join(lines[:index]))
        return entries

    def _next_sequence_unlocked(self, run_dir: Path) -> int:
        logs = self._read_logs_unlocked(run_dir)
        return logs[-1].seq + 1 if logs else 1


__all__ = ["JsonRunStore"]
