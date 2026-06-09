from __future__ import annotations

from collections.abc import Callable
from threading import RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_core.time_utils import utc_now

# ================================================
# Types
# ================================================

RunStatus = Literal[
    "running",
    "queued",
    "created",
    "provisioning",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
]

TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "canceled"})
ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "queued", "created", "provisioning"})


class RunRegistry:
    """Thread-safe in-memory store for background run state.

    Parameterized by the entity-ID field name (e.g. "reeId" or "reviewId")
    and an existence check that should raise HTTPException(404) if the entity
    is not found.
    """

    def __init__(
        self,
        id_field: str,
        require_entity: Callable[[str], None],
        *,
        include_id_in_summary: bool = True,
    ) -> None:
        self._id_field = id_field
        self._require_entity = require_entity
        self._include_id_in_summary = include_id_in_summary
        self._run_store: dict[str, dict[str, dict[str, Any]]] = {}
        self._run_control: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = RLock()

    # ================================================
    # Internal helpers
    # ================================================

    def _append_log_entry(
        self,
        entries: list[dict[str, Any]],
        seq: int,
        stream: str,
        level: str,
        message: str,
    ) -> int:
        entries.append(
            {
                "seq": seq,
                "ts": utc_now(),
                "stream": stream,
                "level": level,
                "message": message,
            }
        )
        return seq + 1

    def _create_run_state(
        self,
        entity_id: str,
        run_id: str,
        operation: str,
        created_at: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any]:
        run_state: dict[str, Any] = {
            "runId": run_id,
            self._id_field: entity_id,
            "operation": operation,
            "status": "running",
            "createdAt": created_at,
            "startedAt": created_at,
            "finishedAt": None,
            "outputs": {},
            "logs": [],
            "request": request_payload,
            "_nextSeq": 1,
        }
        with self._lock:
            self._run_store.setdefault(entity_id, {})[run_id] = run_state
            self._run_control.setdefault(entity_id, {})[run_id] = {
                "cancelRequested": False,
                "thread": None,
                "operation": operation,
            }
        return run_state

    def _set_status(self, entity_id: str, run_id: str, status: str) -> None:
        with self._lock:
            run_state = self._run_store.get(entity_id, {}).get(run_id)
            if not run_state:
                return
            run_state["status"] = status
            if status in TERMINAL_STATUSES:
                run_state["finishedAt"] = utc_now()

    # ================================================
    # Public API
    # ================================================

    def append_log(
        self,
        entity_id: str,
        run_id: str,
        stream: str,
        level: str,
        message: str,
    ) -> None:
        with self._lock:
            run_state = self._run_store.get(entity_id, {}).get(run_id)
            if not run_state:
                return
            next_seq = int(run_state.get("_nextSeq", 1))
            logs = run_state.setdefault("logs", [])
            run_state["_nextSeq"] = self._append_log_entry(logs, next_seq, stream, level, message)

    def update_outputs(self, entity_id: str, run_id: str, outputs: dict[str, Any]) -> None:
        with self._lock:
            run_state = self._run_store.get(entity_id, {}).get(run_id)
            if run_state:
                run_state["outputs"] = outputs

    def is_cancel_requested(self, entity_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(entity_id, {}).get(run_id)
            return bool(control and control.get("cancelRequested"))

    def mark_cancel_requested(self, entity_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(entity_id, {}).get(run_id)
            run_state = self._run_store.get(entity_id, {}).get(run_id)
            if not control or not run_state:
                return False
            control["cancelRequested"] = True
            if run_state.get("status") in ACTIVE_STATUSES:
                run_state["status"] = "canceling"
            return True

    def finalize(
        self,
        entity_id: str,
        run_id: str,
        status: str,
        outputs: dict[str, Any],
    ) -> None:
        if self.is_cancel_requested(entity_id, run_id) and status not in {"failed", "succeeded"}:
            status = "canceled"
        self.update_outputs(entity_id, run_id, outputs)
        self._set_status(entity_id, run_id, status)
        with self._lock:
            run_state = self._run_store.get(entity_id, {}).get(run_id)
            if run_state:
                run_state.pop("_nextSeq", None)

    def start_background(
        self,
        entity_id: str,
        operation: str,
        request_payload: dict[str, Any],
        run_id_prefix: str,
        runner: Callable[[str, str], tuple[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        self._require_entity(entity_id)
        created_at = utc_now()
        run_id = f"{run_id_prefix}-{uuid4().hex}"
        run_state = self._create_run_state(
            entity_id=entity_id,
            run_id=run_id,
            operation=operation,
            created_at=created_at,
            request_payload=request_payload,
        )

        def _worker() -> None:
            try:
                status, outputs = runner(entity_id, run_id)
            except HTTPException as exc:
                self.append_log(
                    entity_id,
                    run_id,
                    "system",
                    "error",
                    str(exc.detail or "Run failed"),
                )
                status = "canceled" if self.is_cancel_requested(entity_id, run_id) else "failed"
                outputs = {}
            except Exception as exc:
                self.append_log(entity_id, run_id, "system", "error", str(exc))
                status = "canceled" if self.is_cancel_requested(entity_id, run_id) else "failed"
                outputs = {}
            self.finalize(entity_id, run_id, status, outputs)

        worker = Thread(target=_worker, daemon=True)
        with self._lock:
            control = self._run_control.get(entity_id, {}).get(run_id)
            if control is not None:
                control["thread"] = worker
        worker.start()
        return run_state

    def run_summary(self, run_state: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "runId",
            "operation",
            "status",
            "createdAt",
            "startedAt",
            "finishedAt",
            "outputs",
        ]
        if self._include_id_in_summary:
            keys.insert(1, self._id_field)
        return {key: run_state[key] for key in keys}

    def get_run_state(self, entity_id: str, run_id: str) -> dict[str, Any]:
        self._require_entity(entity_id)
        with self._lock:
            run_state = self._run_store.get(entity_id, {}).get(run_id)
        if not run_state:
            raise HTTPException(status_code=404, detail="Run not found")
        return run_state
