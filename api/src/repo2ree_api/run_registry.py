from __future__ import annotations

import json
import time
from collections.abc import Callable
from threading import Condition, RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import emit_run_log
from repo2ree_protocol.result import ActionResult, Failure
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
    "queued",
    "provisioning",
    "running",
    "canceling",
    "succeeded",
    "failed",
    "canceled",
]

TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "canceled"})
ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "queued", "provisioning"})

# JSON field name for the REE id in run state and summaries.
_REE_ID_FIELD = "ree_id"


class RunRegistry:
    """Thread-safe in-memory store for background run state, keyed by REE.

    Takes an existence check that should raise HTTPException(404) if the REE
    is not found.
    """

    def __init__(self, require_ree: Callable[[str], None]) -> None:
        self._require_ree = require_ree
        self._run_store: dict[str, dict[str, dict[str, Any]]] = {}
        self._run_control: dict[str, dict[str, dict[str, Any]]] = {}
        self._idempotency_store: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._lock = RLock()
        self._changed = Condition(self._lock)

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
            "run_id": run_id,
            _REE_ID_FIELD: ree_id,
            "operation": operation,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
            "logs": [],
            "request": request_payload,
            "_next_seq": 1,
        }
        with self._lock:
            self._run_store.setdefault(ree_id, {})[run_id] = run_state
            self._run_control.setdefault(ree_id, {})[run_id] = {
                "cancel_requested": False,
                "thread": None,
                "operation": operation,
            }
        return run_state

    def _begin_run(self, ree_id: str, run_id: str, operation: str) -> None:
        """Mark the worker as started: stamp started_at and advance out of 'queued'.

        A provisioning run's working state is "provisioning"; every other run's
        is "running". A cancel that landed while queued set "canceling" — leave
        that in place so the runner's cancel check settles it.
        """
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if not run_state:
                return
            run_state["started_at"] = utc_now()
            if run_state["status"] == "queued":
                run_state["status"] = "provisioning" if operation == "provision" else "running"
                self._changed.notify_all()

    def _set_status(self, ree_id: str, run_id: str, status: str, failure: Failure | None = None) -> None:
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if not run_state:
                return
            run_state["status"] = status
            # Stored (and cleared) together with the status under one lock, so a
            # poller can never observe a terminal `failed` without its failure.
            run_state["failure"] = failure.model_dump() if failure is not None else None
            if status in TERMINAL_STATUSES:
                run_state["finished_at"] = utc_now()
            self._changed.notify_all()

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
            next_seq = int(run_state.get("_next_seq", 1))
            logs = run_state.setdefault("logs", [])
            run_state["_next_seq"] = self._append_log_entry(logs, next_seq, stream, level, message)
            self._changed.notify_all()

    def update_outputs(self, ree_id: str, run_id: str, outputs: dict[str, Any]) -> None:
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if run_state:
                run_state["outputs"] = outputs

    def is_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            return bool(control and control.get("cancel_requested"))

    def mark_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if not control or not run_state:
                return False
            control["cancel_requested"] = True
            if run_state.get("status") in ACTIVE_STATUSES:
                run_state["status"] = "canceling"
                self._changed.notify_all()
            return True

    def finalize(
        self,
        ree_id: str,
        run_id: str,
        status: str,
        outputs: dict[str, Any],
        failure: Failure | None = None,
    ) -> None:
        if self.is_cancel_requested(ree_id, run_id) and status not in {"failed", "succeeded"}:
            status = "canceled"
            # A canceled run carries no failure (mirrors the ActionResult contract).
            failure = None
        self.update_outputs(ree_id, run_id, outputs)
        self._set_status(ree_id, run_id, status, failure)
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
            if run_state:
                run_state.pop("_next_seq", None)

    def _terminal_from_exception(self, ree_id: str, run_id: str, message: str) -> ActionResult:
        """Terminal result for a runner that raised.

        A cancel in flight settles to `canceled`; anything else is an
        `internal` failure that originated here in the API worker thread.
        """
        if self.is_cancel_requested(ree_id, run_id):
            return ActionResult(status="canceled")
        return ActionResult.failed("internal", message, origin="api")

    def start_background(
        self,
        ree_id: str,
        operation: str,
        request_payload: dict[str, Any],
        run_id_prefix: str,
        runner: Callable[[str, str], ActionResult],
        require_ree_exists: bool = True,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # A provisioning run *creates* its REE, so it can't require the REE
        # to already exist; every other run runs against a live REE.
        if require_ree_exists:
            self._require_ree(ree_id)
        normalized_key = (idempotency_key or "").strip()
        fingerprint = json.dumps(request_payload, sort_keys=True, separators=(",", ":"), default=str)
        idempotency_slot = (ree_id, operation, normalized_key)

        # Check and reserve the idempotency slot under the same lock as run
        # creation. A caller retrying after an uncertain HTTP outcome receives
        # the original run; two simultaneous requests cannot both create work.
        with self._lock:
            if normalized_key:
                existing = self._idempotency_store.get(idempotency_slot)
                if existing is not None:
                    existing_run_id, existing_fingerprint = existing
                    if existing_fingerprint != fingerprint:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "idempotency_conflict",
                                "message": "Idempotency key was already used with a different request",
                                "details": {
                                    "operation": operation,
                                    "idempotency_key": normalized_key,
                                    "run_id": existing_run_id,
                                },
                            },
                        )
                    existing_state = self._run_store.get(ree_id, {}).get(existing_run_id)
                    if existing_state is not None:
                        return existing_state

            created_at = utc_now()
            run_id = f"{run_id_prefix}-{uuid4().hex}"
            run_state = self._create_run_state(
                ree_id=ree_id,
                run_id=run_id,
                operation=operation,
                created_at=created_at,
                request_payload=request_payload,
            )
            if normalized_key:
                self._idempotency_store[idempotency_slot] = (run_id, fingerprint)

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
                self._begin_run(ree_id, run_id, operation)
                try:
                    result = runner(ree_id, run_id)
                except HTTPException as exc:
                    message = str(exc.detail or "Run failed")
                    self.append_log(ree_id, run_id, "system", "error", message)
                    result = self._terminal_from_exception(ree_id, run_id, message)
                except Exception as exc:
                    span.record_exception(exc)
                    message = str(exc)
                    self.append_log(ree_id, run_id, "system", "error", message)
                    result = self._terminal_from_exception(ree_id, run_id, message)
                # The run root is the trace a user finds first; make it a
                # self-sufficient wide event by recording the outputs — and the
                # failure, when there is one — here too.
                record_span_facts(span, result.outputs, namespace="output")
                if result.failure is not None:
                    record_span_facts(span, result.failure.model_dump(exclude_none=True), namespace="failure")
                record_command_status(span, result.status)
                self.finalize(ree_id, run_id, result.status, result.outputs, result.failure)

        worker = Thread(target=_worker, daemon=True)
        with self._lock:
            control = self._run_control.get(ree_id, {}).get(run_id)
            if control is not None:
                control["thread"] = worker
        worker.start()
        return run_state

    def run_summary(self, run_state: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "run_id",
            _REE_ID_FIELD,
            "operation",
            "status",
            "created_at",
            "started_at",
            "finished_at",
            "outputs",
            "failure",
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
        summaries.sort(key=lambda summary: (summary["created_at"], summary["run_id"]), reverse=True)
        return summaries

    def get_run_state(self, ree_id: str, run_id: str) -> dict[str, Any]:
        self._require_ree(ree_id)
        with self._lock:
            run_state = self._run_store.get(ree_id, {}).get(run_id)
        if not run_state:
            raise HTTPException(status_code=404, detail="Run not found")
        return run_state

    def observe(
        self,
        ree_id: str,
        run_id: str,
        *,
        after_seq: int,
        wait_seconds: float,
        limit: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str | None, bool]:
        """Wait boundedly for new log entries or terminal run state."""
        self._require_ree(ree_id)
        deadline = time.monotonic() + wait_seconds
        with self._changed:
            while True:
                run_state = self._run_store.get(ree_id, {}).get(run_id)
                if run_state is None:
                    raise HTTPException(status_code=404, detail="Run not found")
                available = [entry for entry in run_state.get("logs", []) if int(entry["seq"]) > after_seq]
                terminal = run_state.get("status") in TERMINAL_STATUSES
                if available or terminal:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._changed.wait(timeout=remaining)

            entries = available[:limit]
            next_cursor = str(entries[-1]["seq"]) if entries else (str(after_seq) if after_seq else None)
            return self.run_summary(run_state), entries, next_cursor, bool(entries or terminal)
