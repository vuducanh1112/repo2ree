from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

from repo2ree_protocol.catalog import ScriptTemplateCatalog
from repo2ree_protocol.command import Command
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import (
    AcceptedFrame,
    BusyFrame,
    ErrorFrame,
    LogFrame,
    LogSink,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    UnknownFrame,
)
from repo2ree_protocol.history import OperationHistory
from repo2ree_protocol.lint import LintReport
from repo2ree_protocol.queries import (
    BundleQuery,
    CatQuery,
    InitRee,
    LintDraftQuery,
    LogQuery,
    ManifestQuery,
    Query,
    ReviewsQuery,
    ShowQuery,
    TemplatesQuery,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree
from repo2ree_ree.review import ReviewSet
from repo2ree_supervisor.client import ReeBusyError, WorkbenchClient, WorkbenchUnavailableError
from repo2ree_supervisor.handle import ReeRoute
from repo2ree_supervisor.locks import ReeLocks
from repo2ree_supervisor.transfers import ReceivedFile
from repo2ree_telemetry.behaviour import events
from repo2ree_telemetry.bootstrap import get_meter, get_tracer
from repo2ree_telemetry.command_line import TRACE_RELAY_ENV
from repo2ree_telemetry.relay import SpanSink
from repo2ree_telemetry.spans import (
    CommandSpanAttrs,
    WorkbenchSpanAttrs,
    command_metric_attrs,
    record_command_status,
    record_exit_code,
    record_failure,
    record_result_boundary,
    record_result_evidence,
    record_span_facts,
)

__all__ = ["CommandDispatcher", "FollowStoppedError"]

BUSY_WAIT = 60.0
RECONNECT_TIMEOUT = 120.0
RECONNECT_POLL = 1.0
PROGRESS_LINES = 50


class FollowStoppedError(RuntimeError):
    pass


def _settled_facts(result: ActionResult) -> events.SettledFacts:
    history = result.history
    interrupted = history is not None and history.operation_status == "interrupted"
    return {
        "status": "interrupted" if interrupted else result.status,
        "commit": history.after_snapshot_id if history else None,
        "record": history.record_digest if history else None,
    }


tracer = get_tracer(__name__)
_meter = get_meter(__name__)


_container_gone_counter = _meter.create_counter(
    "workbench.container_gone",
    description="Number of docker exec failures due to container gone or stopping.",
)
_exec_duration = _meter.create_histogram(
    "workbench.execute_duration_seconds",
    description="Wall-clock duration of workbench command execution (lock held, docker exec running).",
    unit="s",
)
_lock_wait_duration = _meter.create_histogram(
    "workbench.lock_wait_seconds",
    description="Time a dispatch blocked on the per-REE lock before execution (another run in progress).",
    unit="s",
)


class CommandDispatcher:
    def __init__(
        self,
        workbench: WorkbenchClient,
        locks: ReeLocks,
        span_sink: SpanSink | None = None,
        on_unavailable: Callable[[ReeRoute], object] | None = None,
        reroute: Callable[[ReeRoute], ReeRoute | None] | None = None,
    ) -> None:
        self._workbench = workbench
        self._locks = locks
        self._span_sink = span_sink
        self._on_unavailable = on_unavailable or (lambda handle: None)
        self._reroute = reroute or (lambda handle: handle)
        self._followed: dict[tuple[str, str], str] = {}
        self._canceled: set[str] = set()
        self._followed_lock = threading.Lock()

    def dispatch_action(
        self,
        handle: ReeRoute,
        cmd: Command,
        run_id: str,
        log: LogSink,
        context: ExecutionContext | None = None,
        *,
        on_started: Callable[[ExecutionContext], object] | None = None,
        on_session: Callable[[ReeRoute], object] | None = None,
        on_progress: Callable[[int], object] | None = None,
        stop: threading.Event | None = None,
        reconnect_timeout: float | None = RECONNECT_TIMEOUT,
    ) -> ActionResult:
        context = context or ExecutionContext.new(ree_id=handle.ree_id)
        if context.ree_id not in {None, handle.ree_id}:
            raise ValueError("Execution context belongs to another REE")
        context = context.model_copy(update={"ree_id": handle.ree_id})
        with tracer.start_as_current_span("workbench.dispatch_action") as span:
            CommandSpanAttrs(
                operation=str(cmd.operation), run_id=run_id, ree_id=handle.ree_id, execution=context
            ).apply(span)
            WorkbenchSpanAttrs(workbench_id=handle.workbench_id).apply(span)
            record_span_facts(span, cmd.model_dump(), namespace="cmd")
            _lock_t0 = time.monotonic()
            with self._locks(handle.ree_id):
                _lock_wait_duration.record(time.monotonic() - _lock_t0, command_metric_attrs(str(cmd.operation)))
                try:
                    context = self._start(handle, cmd, run_id, context)
                except WorkbenchUnavailableError:
                    self._on_unavailable(handle)
                    raise
            if on_started is not None:
                on_started(context)
            with tracer.start_as_current_span("workbench.execute"):
                _t0 = time.monotonic()
                result = self.follow(
                    handle,
                    context,
                    run_id,
                    log,
                    on_session=on_session,
                    on_progress=on_progress,
                    stop=stop,
                    reconnect_timeout=reconnect_timeout,
                )
                _exec_duration.record(
                    time.monotonic() - _t0, command_metric_attrs(str(cmd.operation), status=result.status)
                )
            record_exit_code(span, result.exit_code)
            record_span_facts(span, result.outputs, namespace="output")
            record_failure(span, result.failure)
            record_command_status(span, result.status)
            record_result_evidence(span, result)
            record_result_boundary(span, "supervisor.received", result)
            return result

    def _start(self, handle: ReeRoute, cmd: Command, run_id: str, context: ExecutionContext) -> ExecutionContext:
        session = self._workbench.session_of(handle.workbench_id)
        if session is None:
            raise WorkbenchUnavailableError(f"workbench {handle.workbench_id!r} is not connected")
        attempt = context.attempt_id
        record = events.start_run_sent(
            attempt,
            partition=handle.ree_id,
            facts={"operation": str(cmd.operation), "run_id": run_id, "session": session},
        )
        context = context.model_copy(update={"dispatch_record": record})
        env = {TRACE_RELAY_ENV: "1"} if self._span_sink is not None else {}
        answered = False

        def answer(message: events.StartRunResponse) -> None:
            nonlocal answered
            answered = True
            events.start_run_received(attempt, message, partition=handle.ree_id)

        try:
            for frame in self._workbench.start_run(
                handle.workbench_id,
                cmd.model_dump_json(),
                run_id,
                env,
                context,
                ree_id=handle.ree_id,
                session=session,
                wait=BUSY_WAIT,
            ):
                if isinstance(frame, AcceptedFrame):
                    answer("accepted")
                    return context
                if isinstance(frame, BusyFrame):
                    answer("busy")
                    raise ReeBusyError(frame.detail)
                if isinstance(frame, UnavailableFrame):
                    answer("unavailable")
                    _container_gone_counter.add(1, command_metric_attrs(str(cmd.operation)))
                    raise WorkbenchUnavailableError(frame.detail)
                if isinstance(frame, ErrorFrame):
                    answer("error")
                    raise RuntimeError(frame.detail)
        except BaseException as exc:
            if not answered:
                events.start_run_abandoned(attempt, partition=handle.ree_id, reason=type(exc).__name__)
            raise
        events.start_run_abandoned(attempt, partition=handle.ree_id, reason="closed_without_response")
        raise WorkbenchUnavailableError(f"{cmd.operation} was not answered")

    def follow(
        self,
        handle: ReeRoute,
        context: ExecutionContext,
        run_id: str,
        log: LogSink,
        *,
        after: int = 0,
        on_session: Callable[[ReeRoute], object] | None = None,
        on_progress: Callable[[int], object] | None = None,
        stop: threading.Event | None = None,
        reconnect_timeout: float | None = None,
    ) -> ActionResult:
        attempt = context.attempt_id
        key = (handle.ree_id, run_id)
        with self._followed_lock:
            self._followed[key] = attempt
        progress = on_progress or (lambda delivered: None)
        try:
            gone_since: float | None = None
            while True:
                if stop is not None and stop.is_set():
                    raise FollowStoppedError(f"stopped following {run_id}")
                handle = self._reroute(handle) or handle
                session = self._workbench.session_of(handle.workbench_id)
                if session is None:
                    gone_since = gone_since or time.monotonic()
                    if reconnect_timeout is not None and time.monotonic() - gone_since > reconnect_timeout:
                        raise WorkbenchUnavailableError(f"workbench {handle.workbench_id!r} did not come back")
                    if stop is not None:
                        stop.wait(RECONNECT_POLL)
                    else:
                        time.sleep(RECONNECT_POLL)
                    continue
                gone_since = None
                if on_session is not None:
                    on_session(handle)
                result, after = self._follow_round(handle, context, run_id, log, after, session, progress)
                progress(after)
                if result is not None:
                    if result.context is not None and result.context.attempt_id != attempt:
                        raise RuntimeError("Executor returned a different execution context")
                    if result.history is not None and result.history.attempt_id != attempt:
                        raise RuntimeError("Executor returned history for a different execution attempt")
                    return result.model_copy(update={"context": context})
        finally:
            with self._followed_lock:
                if self._followed.get(key) == attempt:
                    del self._followed[key]
                self._canceled.discard(attempt)

    def _follow_round(
        self,
        handle: ReeRoute,
        context: ExecutionContext,
        run_id: str,
        log: LogSink,
        after: int,
        session: str,
        progress: Callable[[int], object],
    ) -> tuple[ActionResult | None, int]:
        attempt = context.attempt_id
        events.follow_run_sent(attempt, partition=handle.ree_id, facts={"run_id": run_id, "session": session})
        answered = False
        try:
            for frame in self._workbench.follow_run(
                handle.workbench_id, attempt, after, ree_id=handle.ree_id, session=session
            ):
                if isinstance(frame, LogFrame):
                    log(frame.stream, frame.level, frame.message)
                    after += 1
                elif isinstance(frame, SpanFrame):
                    if self._span_sink is not None:
                        self._span_sink([frame.payload])
                    after += 1
                elif isinstance(frame, ResultFrame):
                    answered = True
                    events.follow_run_received(
                        attempt, "settled", partition=handle.ree_id, facts=_settled_facts(frame.result)
                    )
                    return frame.result, after
                elif isinstance(frame, UnknownFrame):
                    answered = True
                    events.follow_run_received(attempt, "unknown", partition=handle.ree_id)
                    failed = ActionResult.failed("internal", frame.detail, origin="workbench", retryable=True)
                    return failed, after
                elif isinstance(frame, ErrorFrame):
                    answered = True
                    events.follow_run_received(attempt, "error", partition=handle.ree_id)
                    raise RuntimeError(frame.detail)
                elif isinstance(frame, UnavailableFrame):
                    break
                if after % PROGRESS_LINES == 0:
                    progress(after)
        except WorkbenchUnavailableError as exc:
            events.follow_run_abandoned(attempt, partition=handle.ree_id, reason=type(exc).__name__)
            return None, after
        except BaseException as exc:
            if not answered:
                events.follow_run_abandoned(attempt, partition=handle.ree_id, reason=type(exc).__name__)
            raise
        events.follow_run_abandoned(attempt, partition=handle.ree_id, reason="session_ended")
        return None, after

    def cancel_run(self, handle: ReeRoute, run_id: str) -> None:
        with self._followed_lock:
            attempt = self._followed.get((handle.ree_id, run_id))
            first = attempt is not None and attempt not in self._canceled
            if first and attempt is not None:
                self._canceled.add(attempt)
        session = self._workbench.session_of(handle.workbench_id)
        if not first or attempt is None or session is None:
            self._workbench.cancel_run(handle.workbench_id, run_id, ree_id=handle.ree_id)
            return
        record = events.cancel_run_sent(attempt, partition=handle.ree_id, facts={"run_id": run_id, "session": session})
        try:
            self._workbench.cancel_run(handle.workbench_id, run_id, ree_id=handle.ree_id, record=record)
        except WorkbenchUnavailableError as exc:
            events.cancel_run_abandoned(attempt, partition=handle.ree_id, reason=type(exc).__name__)
            raise
        except RuntimeError:
            events.cancel_run_received(attempt, "error", partition=handle.ree_id)
            raise
        except BaseException as exc:
            events.cancel_run_abandoned(attempt, partition=handle.ree_id, reason=type(exc).__name__)
            raise
        events.cancel_run_received(attempt, "done", partition=handle.ree_id)

    def dispatch_query(self, handle: ReeRoute, query: Query, *, timeout: int = 30) -> bytes:
        return self._workbench.exec_query(handle.workbench_id, query, timeout=timeout, ree_id=handle.ree_id)

    def _query_json(self, handle: ReeRoute, query: Query) -> dict[str, Any]:
        parsed: dict[str, Any] = json.loads(self.dispatch_query(handle, query))
        return parsed

    def get_ree_manifest(self, handle: ReeRoute) -> Ree:
        return Ree.model_validate(self._query_json(handle, ManifestQuery()))

    def get_ree_document(self, handle: ReeRoute) -> WorkbenchReeDocument:
        return WorkbenchReeDocument.model_validate(self._query_json(handle, ShowQuery()))

    def get_ree_state(self, handle: ReeRoute) -> WorkbenchReeDocument:
        return WorkbenchReeDocument.model_validate(self._query_json(handle, ShowQuery(summary=True)))

    def get_history(self, handle: ReeRoute) -> OperationHistory:
        return OperationHistory.model_validate(self._query_json(handle, LogQuery()))

    def get_reviews(self, handle: ReeRoute) -> ReviewSet:
        return ReviewSet.model_validate(self._query_json(handle, ReviewsQuery()))

    def list_script_templates(self, handle: ReeRoute) -> ScriptTemplateCatalog:
        return ScriptTemplateCatalog.model_validate(self._query_json(handle, TemplatesQuery()))

    def lint_draft(self, handle: ReeRoute, query: LintDraftQuery) -> LintReport:
        return LintReport.model_validate(self._query_json(handle, query))

    def read_ree_file_bytes(self, handle: ReeRoute, path: str) -> bytes:
        return self.dispatch_query(handle, CatQuery(path=path), timeout=120)

    def build_archive(self, handle: ReeRoute) -> ReceivedFile:
        with self._locks(handle.ree_id):
            return self._workbench.exec_upload(handle.workbench_id, BundleQuery(), timeout=600, ree_id=handle.ree_id)

    def copy_to_workbench(self, handle: ReeRoute, host_path: str, workbench_path: str) -> None:
        self._workbench.copy_in(handle.workbench_id, host_path, workbench_path, ree_id=handle.ree_id)

    def init_ree(self, handle: ReeRoute, name: str) -> None:
        with self._locks(handle.ree_id):
            self._workbench.init_ree(
                handle.workbench_id,
                InitRee(name=name),
                ree_id=handle.ree_id,
            )

    def delete_ree(self, handle: ReeRoute) -> None:
        with self._locks(handle.ree_id):
            self._workbench.delete_ree(handle.workbench_id, handle.ree_id)
