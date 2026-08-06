from __future__ import annotations

import json
import time
from collections.abc import Callable
from threading import Condition, RLock, Thread
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import emit_run_log
from repo2ree_protocol.result import ActionResult, Failure, FailureCategory
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    command_metric_attrs,
    current_span_link,
    get_meter,
    get_tracer,
    record_command_status,
    record_failure,
    record_span_facts,
)

tracer = get_tracer(__name__)
_meter = get_meter(__name__)

# ================================================
# Metrics
# ================================================
#
# The background-run counterpart of the ``ree.command`` instruments in
# workbench/commands.py, named and attributed the same way so one query spans
# both halves of the API's work. Spans already carry each run as a wide event;
# these exist for the questions a trace store answers badly — run rate, error
# rate, and duration distribution over a window.

_run_counter = _meter.create_counter(
    "ree.run",
    description="Number of background runs settled, by operation and terminal status.",
)
_run_duration = _meter.create_histogram(
    "ree.run_duration_seconds",
    description="Wall-clock duration of a background run, from worker start to terminal status.",
    unit="s",
)
_runs_active = _meter.create_up_down_counter(
    "ree.run_active",
    description="Background runs currently executing, by operation.",
)
# The two idempotency outcomes are separate instruments rather than one counter
# with an outcome attribute: they answer different questions (a replay is a
# client retrying correctly; a conflict is a client reusing a key it shouldn't)
# and only the second is ever alertable.
_run_replay_counter = _meter.create_counter(
    "ree.run_idempotent_replay",
    description="Number of run requests answered with an existing run because their idempotency key matched.",
)
_run_idempotency_conflict_counter = _meter.create_counter(
    "ree.run_idempotency_conflict",
    description="Number of run requests rejected because their idempotency key was reused with a different payload.",
)

# ================================================
# Types
# ================================================

TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "canceled"})
ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "queued", "provisioning"})

# JSON field name for the REE id in run state and summaries.
_REE_ID_FIELD = "ree_id"

# HTTP status → the failure category it already means.
#
# A route that raised a typed 4xx knew what kind of failure it had; the worker
# thread that catches it does not, and re-minting it as `internal` would tell
# the client the fault was repo2ree's when the client is the one who can fix
# it. The contract is that a layer enriches a failure rather than collapsing it
# (see repo2ree_protocol.result.Failure), and this is where that has to hold
# for a run started over HTTP.
_STATUS_CATEGORIES: dict[int, FailureCategory] = {
    400: "validation",
    404: "precondition",
    409: "conflict",
    412: "conflict",
    413: "validation",
    422: "validation",
    502: "unavailable",
    503: "unavailable",
    504: "timeout",
}
# The statuses whose meaning is "try again" — same set the HTTP error envelope
# in main.py defaults `retryable` from, so a run failure and the immediate
# response to the request that started it agree.
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 502, 503, 504})


def _failure_from_http_exception(exc: HTTPException) -> Failure:
    """The typed failure an ``HTTPException`` raised by a runner already carries.

    Routes raise the structured error envelope through ``detail``. Stringifying
    that dict produced a failure whose message was a Python repr; instead the
    envelope's own message becomes the message, and everything else on it —
    ``code``, ``details`` — is preserved under ``Failure.details`` where a
    client can still read it.
    """
    default_category: FailureCategory = "validation" if exc.status_code < 500 else "internal"
    category = _STATUS_CATEGORIES.get(exc.status_code, default_category)
    retryable = exc.status_code in _RETRYABLE_STATUSES

    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("code") or "Run failed")
        carried = {key: value for key, value in detail.items() if key != "message" and value is not None}
    else:
        message = str(detail or "Run failed")
        carried = {}
    carried["http_status"] = exc.status_code

    return Failure(category=category, message=message, retryable=retryable, origin="api", details=carried)


class RunRegistry:
    """Thread-safe in-memory store for background run state, keyed by REE.

    The supplied check guards creation of new work. Historical run reads are
    resolved from this registry itself and deliberately do not probe workbench
    liveness, so logs remain observable after deletion or agent disconnect.
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
        outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_state: dict[str, Any] = {
            "run_id": run_id,
            _REE_ID_FIELD: ree_id,
            "operation": operation,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
            # Seeded with whatever the route already knows this run is *about* —
            # an id it minted itself, say. A queued run is a real answer to "what
            # did my request start", and a caller that has to wait for the run to
            # execute before it can learn that cannot act on its own request.
            # Command outputs replace these wholesale once there are any.
            "outputs": dict(outputs or {}),
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
    ) -> str:
        """Settle a run and return the status actually stored.

        The settled status is not always the one passed in — a cancel in flight
        rewrites it — and the caller's metrics have to report what a poller will
        see, not what the runner proposed.
        """
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
        return status

    def _terminal_from_failure(self, ree_id: str, run_id: str, failure: Failure) -> ActionResult:
        """Terminal result for a runner that raised, carrying ``failure``.

        A cancel in flight settles to `canceled` — which carries no failure, per
        the ActionResult contract — and anything else fails with the typed
        failure the caller derived from what was actually raised.
        """
        if self.is_cancel_requested(ree_id, run_id):
            return ActionResult(status="canceled")
        return ActionResult(status="failed", exit_code=1, failure=failure)

    def _terminal_from_exception(self, ree_id: str, run_id: str, message: str) -> ActionResult:
        """Terminal result for a runner that raised something untyped.

        The last frame of a background run: nothing above it can report, and an
        exception that reached here was not anticipated by the code that raised
        it, so it is an `internal` fault originating in this API worker thread.
        """
        return self._terminal_from_failure(
            ree_id,
            run_id,
            Failure(category="internal", message=message, origin="api"),
        )

    def start_background(
        self,
        ree_id: str,
        operation: str,
        request_payload: dict[str, Any],
        run_id_prefix: str,
        runner: Callable[[str, str], ActionResult],
        require_ree_exists: bool = True,
        idempotency_key: str | None = None,
        initial_outputs: dict[str, Any] | None = None,
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
                        _run_idempotency_conflict_counter.add(1, command_metric_attrs(operation))
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
                        _run_replay_counter.add(1, command_metric_attrs(operation))
                        return existing_state

            created_at = utc_now()
            run_id = f"{run_id_prefix}-{uuid4().hex}"
            run_state = self._create_run_state(
                ree_id=ree_id,
                run_id=run_id,
                operation=operation,
                created_at=created_at,
                request_payload=request_payload,
                outputs=initial_outputs,
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
                # Measured from here, not from the request: the queue between
                # them is a thread spawn, and what an operator wants back is how
                # long the work took.
                started = time.monotonic()
                active_attrs = command_metric_attrs(operation)
                _runs_active.add(1, active_attrs)
                try:
                    try:
                        result = runner(ree_id, run_id)
                    except HTTPException as exc:
                        failure = _failure_from_http_exception(exc)
                        # The envelope's message, not the dict it arrived in:
                        # this line is what a user reads in the run log.
                        self.append_log(ree_id, run_id, "system", "error", failure.message)
                        result = self._terminal_from_failure(ree_id, run_id, failure)
                    except Exception as exc:  # noqa: BLE001 — the registry is the last frame of a background run; nothing above it can report
                        span.record_exception(exc)
                        message = str(exc)
                        self.append_log(ree_id, run_id, "system", "error", message)
                        result = self._terminal_from_exception(ree_id, run_id, message)
                    # The run root is the trace a user finds first; make it a
                    # self-sufficient wide event by recording the outputs — and the
                    # failure, when there is one — here too.
                    record_span_facts(span, result.outputs, namespace="output")
                    record_failure(span, result.failure)
                    record_command_status(span, result.status)
                    settled = self.finalize(ree_id, run_id, result.status, result.outputs, result.failure)
                    # Attributed with the *settled* status, so the counter agrees
                    # with what a poller reads back and with the run's own span.
                    terminal_attrs = command_metric_attrs(operation, status=settled)
                    _run_duration.record(time.monotonic() - started, terminal_attrs)
                    _run_counter.add(1, terminal_attrs)
                finally:
                    # In the finally so a raise anywhere above cannot strand the
                    # gauge one run high for the life of the process.
                    _runs_active.add(-1, active_attrs)

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

    def list_runs(self, ree_id: str) -> list[dict[str, Any]]:
        """Summaries of every recorded run for ree_id, newest first."""
        with self._lock:
            run_states = list(self._run_store.get(ree_id, {}).values())
        summaries = [self.run_summary(run_state) for run_state in run_states]
        summaries.sort(key=lambda summary: (summary["created_at"], summary["run_id"]), reverse=True)
        return summaries

    def get_run_state(self, ree_id: str, run_id: str) -> dict[str, Any]:
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
