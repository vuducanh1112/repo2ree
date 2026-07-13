from __future__ import annotations

from collections.abc import Callable
from threading import RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import emit_run_log
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    current_span_link,
    get_tracer,
    record_command_status,
    record_span_facts,
)

tracer = get_tracer(__name__)

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

# JSON field name for the REE id in run state and summaries.
_REE_ID_FIELD = "reeId"


class RunRegistry:
    """Thread-safe in-memory store for background run state, keyed by REE.

    Takes an existence check that should raise HTTPException(404) if the REE
    is not found.
    """

    def __init__(self, require_ree: Callable[[str], None]) -> None:
        self._require_ree = require_ree
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
        ree_id: str,
        run_id: str,
        operation: str,
        created_at: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any]:
        run_state: dict[str, Any] = {
            "runId": run_id,
            _REE_ID_FIELD: ree_id,
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
            self._run_store.setdefault(ree_id, {})[run_id] = run_state
            self._run_control.setdefault(ree_id, {})[run_id] = {
                "cancelRequested": False,
                "thread": None,
                "operation": operation,
            }
        return run_state

    def _set_status(self, ree_id: str, run_id: str, status: str) -> None:
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
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
        ree_id: str,
        run_id: str,
        stream: str,
        level: str,
        message: str,
    ) -> None:
        # Every run-log line passes through here, still inside the span that
        # produced it — export it to the collector (durable, trace-correlated)
        # before storing it in the in-memory store that serves the API.
        emit_run_log(ree_id, run_id, stream, level, message)
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if not run_state:
                return
            next_seq = int(run_state.get("_nextSeq", 1))
            logs = run_state.setdefault("logs", [])
            run_state["_nextSeq"] = self._append_log_entry(logs, next_seq, stream, level, message)

    def update_outputs(self, ree_id: str, run_id: str, outputs: dict[str, Any]) -> None:
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if run_state:
                run_state["outputs"] = outputs

    def is_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            return bool(control and control.get("cancelRequested"))

    def mark_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if not control or not run_state:
                return False
            control["cancelRequested"] = True
            if run_state.get("status") in ACTIVE_STATUSES:
                run_state["status"] = "canceling"
            return True

    def finalize(
        self,
        ree_id: str,
        run_id: str,
        status: str,
        outputs: dict[str, Any],
    ) -> None:
        if self.is_cancel_requested(ree_id, run_id) and status not in {"failed", "succeeded"}:
            status = "canceled"
        self.update_outputs(ree_id, run_id, outputs)
        self._set_status(ree_id, run_id, status)
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if run_state:
                run_state.pop("_nextSeq", None)

    def start_background(
        self,
        ree_id: str,
        operation: str,
        request_payload: dict[str, Any],
        run_id_prefix: str,
        runner: Callable[[str, str], tuple[str, dict[str, Any]]],
        require_ree_exists: bool = True,
    ) -> dict[str, Any]:
        # A provisioning run *creates* its REE, so it can't require the REE
        # to already exist; every other run runs against a live REE.
        if require_ree_exists:
            self._require_ree(ree_id)
        created_at = utc_now()
        run_id = f"{run_id_prefix}-{uuid4().hex}"
        run_state = self._create_run_state(
            ree_id=ree_id,
            run_id=run_id,
            operation=operation,
            created_at=created_at,
            request_payload=request_payload,
        )

        # Capture the originating request span here, on the request thread,
        # before we hand off to the worker — by the time the worker runs the
        # request context is gone. Linked (not parented) so the run anchors its
        # own trace while staying navigable from the request that started it.
        request_link = current_span_link()

        def _worker() -> None:
            # Root span for the background run: it outlives the HTTP response, so
            # it anchors its own trace. The dispatch_action span (same thread)
            # nests under it.
            links = [request_link] if request_link is not None else None
            with tracer.start_as_current_span(f"run.{operation}", links=links) as span:
                CommandSpanAttrs(operation=operation, run_id=run_id, ree_id=ree_id).apply(span)
                try:
                    status, outputs = runner(ree_id, run_id)
                except HTTPException as exc:
                    self.append_log(
                        ree_id,
                        run_id,
                        "system",
                        "error",
                        str(exc.detail or "Run failed"),
                    )
                    status = "canceled" if self.is_cancel_requested(ree_id, run_id) else "failed"
                    outputs = {}
                except Exception as exc:
                    span.record_exception(exc)
                    self.append_log(ree_id, run_id, "system", "error", str(exc))
                    status = "canceled" if self.is_cancel_requested(ree_id, run_id) else "failed"
                    outputs = {}
                # The run root is the trace a user finds first; make it a
                # self-sufficient wide event by recording the outputs here too.
                record_span_facts(span, outputs, namespace="output")
                record_command_status(span, status)
                self.finalize(ree_id, run_id, status, outputs)

        worker = Thread(target=_worker, daemon=True)
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            if control is not None:
                control["thread"] = worker
        worker.start()
        return run_state

    def run_summary(self, run_state: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "runId",
            _REE_ID_FIELD,
            "operation",
            "status",
            "createdAt",
            "startedAt",
            "finishedAt",
            "outputs",
        ]
        return {key: run_state[key] for key in keys}

    def has_runs(self, ree_id: str) -> bool:
        """True if any run is recorded for ree_id (even before it fully exists).

        Lets the REE-existence check accept a REE that is still being
        created by an in-flight run (e.g. a provisioning run that owns the
        workbench's creation), so its logs are readable while it provisions.
        """
        with self._lock:
            return bool(self._run_store.get(ree_id))

    def list_runs(self, ree_id: str) -> list[dict[str, Any]]:
        """Summaries of every recorded run for ree_id, newest first."""
        self._require_ree(ree_id)
        with self._lock:
            run_states = list(self._run_store.get(ree_id, {}).values())
        summaries = [self.run_summary(run_state) for run_state in run_states]
        summaries.sort(key=lambda summary: summary["createdAt"], reverse=True)
        return summaries

    def get_run_state(self, ree_id: str, run_id: str) -> dict[str, Any]:
        self._require_ree(ree_id)
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
        if not run_state:
            raise HTTPException(status_code=404, detail="Run not found")
        return run_state
