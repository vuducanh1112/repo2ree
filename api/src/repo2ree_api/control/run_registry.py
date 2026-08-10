from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Condition, RLock
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_api.contracts import RunOperation, RunStatus
from repo2ree_api.storage.run_store import IdempotencyConflictError, RunStore, StoredRun
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
_log = logging.getLogger(__name__)

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
ACTIVE_STATUSES: frozenset[str] = frozenset({"running", "queued", "provisioning", "canceling"})

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
    """Durable background-run state machine for a single API process."""

    def __init__(
        self,
        require_ree: Callable[[str], None],
        store: RunStore,
        *,
        max_workers: int,
    ) -> None:
        self._require_ree = require_ree
        self._store = store
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="repo2ree-run")
        self._run_control: dict[str, Future[None]] = {}
        self._lock = RLock()
        self._changed = Condition(self._lock)

    def startup(self) -> None:
        """Settle work that a previous API process could not finish."""
        interrupted = self._store.interrupt_incomplete()
        if interrupted:
            with self._changed:
                self._changed.notify_all()

    def shutdown(self) -> None:
        """Drain the bounded worker pool during orderly API shutdown."""
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _snapshot(self, run: StoredRun, *, include_logs: bool) -> dict[str, Any]:
        state = run.model_dump(
            exclude={"schema_version", "cancel_requested_at", "idempotency_key", "request_fingerprint"}
        )
        state["logs"] = (
            [entry.model_dump() for entry in self._store.list_logs(run.ree_id, run.run_id, after_seq=0)]
            if include_logs
            else []
        )
        return state

    def _begin_run(self, ree_id: str, run_id: str) -> None:
        with self._changed:
            if self._store.begin(ree_id, run_id) is not None:
                self._changed.notify_all()

    def append_log(self, ree_id: str, run_id: str, stream: str, level: str, message: str) -> None:
        emit_run_log(ree_id, run_id, stream, level, message)
        with self._changed:
            if (
                self._store.append_log(
                    ree_id,
                    run_id,
                    stream=stream,
                    level=level,
                    message=message,
                )
                is not None
            ):
                self._changed.notify_all()

    def list_run_logs(
        self,
        ree_id: str,
        run_id: str,
        *,
        after_seq: int,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if self._store.get(ree_id, run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return [entry.model_dump() for entry in self._store.list_logs(ree_id, run_id, after_seq=after_seq, limit=limit)]

    def update_outputs(self, ree_id: str, run_id: str, outputs: dict[str, Any]) -> None:
        self._store.update_outputs(ree_id, run_id, outputs)

    def is_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        return self._store.is_cancel_requested(ree_id, run_id)

    def mark_cancel_requested(self, ree_id: str, run_id: str) -> bool:
        with self._changed:
            updated = self._store.request_cancel(ree_id, run_id)
            if updated is None:
                return False
            self._changed.notify_all()
            return True

    def finalize(
        self,
        ree_id: str,
        run_id: str,
        status: RunStatus,
        outputs: dict[str, Any],
        failure: Failure | None = None,
    ) -> str:
        """Atomically settle a run and return the status actually stored."""
        with self._changed:
            stored = self._store.finalize(
                ree_id,
                run_id,
                status=status,
                outputs=outputs,
                failure=failure,
            )
            if stored is None:
                return status
            self._changed.notify_all()
            return stored.status

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
        operation: RunOperation,
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
        # Capture request context before persistence: if the tracing provider
        # itself is broken, no durable queued run is left without a worker.
        request_link = current_span_link()
        run_id = f"{run_id_prefix}-{uuid4().hex}"
        proposed = StoredRun(
            run_id=run_id,
            ree_id=ree_id,
            operation=operation,
            status="queued",
            created_at=utc_now(),
            request=request_payload,
            outputs=dict(initial_outputs or {}),
            idempotency_key=normalized_key or None,
            request_fingerprint=fingerprint if normalized_key else None,
        )
        try:
            stored, created = self._store.create_idempotent(proposed)
        except IdempotencyConflictError as exc:
            _run_idempotency_conflict_counter.add(1, command_metric_attrs(operation))
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "Idempotency key was already used with a different request",
                    "details": {
                        "operation": operation,
                        "idempotency_key": normalized_key,
                        "run_id": exc.existing.run_id,
                    },
                },
            ) from exc
        if not created:
            _run_replay_counter.add(1, command_metric_attrs(operation))
            return self._snapshot(stored, include_logs=True)
        run_id = stored.run_id

        def _instrumented_worker() -> None:
            # Root span for the background run: it outlives the HTTP response, so
            # it anchors its own trace. The dispatch_action span (same thread)
            # nests under it.
            links = [request_link] if request_link is not None else None
            with tracer.start_as_current_span(f"run.{operation}", links=links) as span:
                CommandSpanAttrs(operation=operation, run_id=run_id, ree_id=ree_id).apply(span)
                self._begin_run(ree_id, run_id)
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

        def _worker() -> None:
            """Last-resort boundary for tracing, metrics, and persistence faults."""
            try:
                _instrumented_worker()
            except Exception as exc:  # noqa: BLE001 -- last frame of a background Future
                message = str(exc) or type(exc).__name__
                current = self._store.get(ree_id, run_id)
                if current is not None and current.status in TERMINAL_STATUSES:
                    # Telemetry can fail after durable finalization. Report that
                    # operational fault without rewriting a completed command.
                    _log.exception("post-finalization worker failure for run %s", run_id)
                    return
                try:
                    self.append_log(ree_id, run_id, "system", "error", message)
                except Exception:  # noqa: BLE001 -- preserve the original worker failure
                    _log.exception("failed to append terminal log for run %s", run_id)
                terminal = self._terminal_from_exception(ree_id, run_id, message)
                # Let a storage failure escape into the Future: a failed store
                # cannot represent its own failure, but control cleanup still
                # happens through the Future's done callback.
                self.finalize(ree_id, run_id, terminal.status, terminal.outputs, terminal.failure)

        try:
            future = self._executor.submit(_worker)
        except RuntimeError as exc:
            # Executor shutdown or thread creation failure happened before this
            # request returned. Preserve the durable run, but settle it instead
            # of leaving a queued record that can never start.
            failure = Failure(
                category="internal",
                message=f"Background run could not be scheduled: {exc}",
                retryable=True,
                origin="api",
            )
            try:
                self.append_log(ree_id, run_id, "system", "error", failure.message)
            except Exception:  # noqa: BLE001 -- finalization must still run
                _log.exception("failed to append scheduling failure for run %s", run_id)
            self.finalize(ree_id, run_id, "failed", {}, failure)
            failed = self._store.get(ree_id, run_id)
            if failed is None:
                raise
            return self._snapshot(failed, include_logs=True)
        with self._lock:
            self._run_control[run_id] = future

        def _forget(_future: Future[None]) -> None:
            with self._lock:
                self._run_control.pop(run_id, None)

        future.add_done_callback(_forget)
        return self._snapshot(stored, include_logs=True)

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
        return [self.run_summary(self._snapshot(run, include_logs=False)) for run in self._store.list_runs(ree_id)]

    def get_run_state(self, ree_id: str, run_id: str) -> dict[str, Any]:
        run = self._store.get(ree_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return self._snapshot(run, include_logs=True)

    def get_run_summary(self, ree_id: str, run_id: str) -> dict[str, Any]:
        run = self._store.get(ree_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return self.run_summary(self._snapshot(run, include_logs=False))

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
                run = self._store.get(ree_id, run_id)
                if run is None:
                    raise HTTPException(status_code=404, detail="Run not found")
                available = self.list_run_logs(ree_id, run_id, after_seq=after_seq, limit=limit)
                terminal = run.status in TERMINAL_STATUSES
                if available or terminal:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._changed.wait(timeout=remaining)

            entries = available[:limit]
            next_cursor = str(entries[-1]["seq"]) if entries else (str(after_seq) if after_seq else None)
            return (
                self.run_summary(self._snapshot(run, include_logs=False)),
                entries,
                next_cursor,
                bool(entries or terminal),
            )
