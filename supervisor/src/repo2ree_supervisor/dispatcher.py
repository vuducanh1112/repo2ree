"""Typed commands and queries sent to the workbench an REE is served by.

The dispatcher consumes the workbench's ``Frame`` stream, forwards log and span frames as they
arrive, journals each dispatch exchange, and returns the terminal result frame's ``ActionResult``.
It never sets up or tears down a workbench; it is told, through ``on_unavailable``, to let whoever
does know that one stopped answering.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

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
from repo2ree_protocol.queries import (
    BUILD_ARCHIVE,
    GET_HISTORY,
    GET_REE_DOCUMENT,
    GET_REE_DOCUMENT_SUMMARY,
    GET_REE_MANIFEST,
    GET_REVIEWS,
    READ_REE_FILE,
    READ_REE_FILE_PATH,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree
from repo2ree_ree.review import ReviewSet
from repo2ree_ree.workbench_environment import EnvironmentBackend
from repo2ree_supervisor.client import ReeBusyError, WorkbenchClient, WorkbenchUnavailableError
from repo2ree_supervisor.handle import ReeRoute
from repo2ree_supervisor.locks import ReeLocks
from repo2ree_supervisor.transfers import ReceivedFile
from repo2ree_telemetry.behaviour import events
from repo2ree_telemetry.bootstrap import get_meter, get_tracer
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

# How long a command waits for another in its REE to end before it is refused as busy: the commands an
# author's editor sends one after another overlap, and wait for each other.
BUSY_WAIT = 60.0
# How long a command waits for its store's workbench to be back by default, and how often it looks.
RECONNECT_TIMEOUT = 120.0
RECONNECT_POLL = 1.0
# How often, in log lines, the caller hears how far it has read.
PROGRESS_LINES = 50


class FollowStoppedError(RuntimeError):
    """The caller stopped following a command, which runs on."""


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

# ================================================
# Metrics
# ================================================

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
        # Where the REE's commands go now: a command is followed on whichever workbench serves its store.
        self._reroute = reroute or (lambda handle: handle)
        # The attempt each followed run is, so a cancel of it is journaled against that attempt, once.
        self._followed: dict[tuple[str, str], str] = {}
        self._canceled: set[str] = set()
        self._followed_lock = threading.Lock()

    # ------------------------------------------------
    # Action dispatch
    # ------------------------------------------------

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
        """Start a typed Command in the workbench and follow it to its end, streaming its log to ``log``.

        It is followed across sessions, waiting up to ``reconnect_timeout`` (None: for as long as it
        takes) for its store's workbench to be back. ``on_started`` learns the context it was started
        with, and ``on_progress`` how many of its log lines were delivered. A set ``stop`` ends the
        follow with ``FollowStoppedError``; the command runs on.
        """
        context = context or ExecutionContext.new(ree_id=handle.ree_id)
        if context.ree_id not in {None, handle.ree_id}:
            raise ValueError("Execution context belongs to another REE")
        context = context.model_copy(update={"ree_id": handle.ree_id})
        with tracer.start_as_current_span("workbench.dispatch_action") as span:
            CommandSpanAttrs(
                operation=str(cmd.operation), run_id=run_id, ree_id=handle.ree_id, execution=context
            ).apply(span)
            WorkbenchSpanAttrs(workbench_id=handle.workbench_id).apply(span)
            # The whole command as dispatched, recorded before it runs: a command that is killed
            # still carries what it was asked to do.
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
        """One ``start_run`` exchange, journaled before it leaves and with its one answer; the context sent.

        The request names the session it is sent on, and is sent on no other. The attempt and the
        executor cite the request's journal record, which the context carries to them.
        """
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
        env = {"TRACE_RELAY": "1"} if self._span_sink is not None else {}
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
        """Follow a started command until it ends, one ``follow_run`` round per session, from log line ``after``."""
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
        """One ``follow_run`` exchange: how the command ended (None if its session ended first), and lines delivered.

        Log and span frames are forwarded as they arrive, so a command that hangs still shows what
        it said before it stopped.
        """
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
        """Ask the workbench executor to stop a running action.

        This deliberately does not take the per-REE lock. A cancel of a command being followed is
        journaled against its attempt, once; any other is only sent.
        """
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

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: ReeRoute, *argv: str, locked: bool = False, timeout: int = 30) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes.

        ``argv`` is a ``repo2ree-exec`` subcommand (e.g. ``get-ree-manifest``);
        the workbench service prepends the bench's executor entry point. Set
        ``locked`` for
        queries that must observe a consistent snapshot — they take the per-REE
        lock so no mutating action runs concurrently. Plain reads leave it off
        and run unsynchronised. ``timeout`` bounds the exec itself; raise it for
        queries whose output scales with the REE (archives, large artifacts).
        """
        exec_argv = list(argv)
        if locked:
            with self._locks(handle.ree_id):
                return self._workbench.exec_query(handle.workbench_id, exec_argv, timeout=timeout, ree_id=handle.ree_id)
        return self._workbench.exec_query(handle.workbench_id, exec_argv, timeout=timeout, ree_id=handle.ree_id)

    def dispatch_query_stream(
        self, handle: ReeRoute, *argv: str, locked: bool = False, timeout: int = 30
    ) -> Iterator[bytes]:
        """Run a read-only CLI subcommand and stream stdout bytes."""
        exec_argv = list(argv)

        def query() -> Iterator[bytes]:
            return self._workbench.exec_query_stream(
                handle.workbench_id, exec_argv, timeout=timeout, ree_id=handle.ree_id
            )

        def stream() -> Iterator[bytes]:
            if locked:
                with self._locks(handle.ree_id):
                    yield from query()
                return
            yield from query()

        return stream()

    def _query_json(self, handle: ReeRoute, *argv: str) -> dict[str, Any]:
        """Run a read-only CLI subcommand and parse its stdout as a JSON object.

        The one place the workbench's untyped JSON becomes a typed value, so the
        ``Any`` that ``json.loads`` returns is narrowed once rather than at each
        of the five call sites below.
        """
        parsed: dict[str, Any] = json.loads(self.dispatch_query(handle, *argv))
        return parsed

    def get_ree_manifest(self, handle: ReeRoute) -> Ree:
        return Ree.model_validate(self._query_json(handle, GET_REE_MANIFEST))

    def get_ree_document(self, handle: ReeRoute) -> WorkbenchReeDocument:
        return WorkbenchReeDocument.model_validate(self._query_json(handle, GET_REE_DOCUMENT))

    def get_ree_state(self, handle: ReeRoute) -> WorkbenchReeDocument:
        """Return composed REE state without embedding text file contents."""
        return WorkbenchReeDocument.model_validate(self._query_json(handle, GET_REE_DOCUMENT, GET_REE_DOCUMENT_SUMMARY))

    def get_history(self, handle: ReeRoute) -> OperationHistory:
        return OperationHistory.model_validate(self._query_json(handle, GET_HISTORY))

    def get_reviews(self, handle: ReeRoute) -> ReviewSet:
        return ReviewSet.model_validate(self._query_json(handle, GET_REVIEWS))

    def read_ree_file_bytes(self, handle: ReeRoute, path: str) -> bytes:
        # REE files can include large experiment environment and result artifacts.
        return self.dispatch_query(handle, READ_REE_FILE, READ_REE_FILE_PATH, path, timeout=120)

    def build_archive(self, handle: ReeRoute) -> ReceivedFile:
        """The REE's archive as a file on the control plane; the caller removes it.

        Built and uploaded beside the control socket (``exec_upload``), under the
        per-REE lock, which is released once the file has arrived — never held for
        as long as a client takes to download it. Zipping and sending scale with
        the REE's size, hence the generous timeout."""
        with self._locks(handle.ree_id):
            return self._workbench.exec_upload(handle.workbench_id, [BUILD_ARCHIVE], timeout=600, ree_id=handle.ree_id)

    def copy_to_workbench(self, handle: ReeRoute, host_path: str, workbench_path: str) -> None:
        """Copy a control-plane-local file into the workbench.

        ``host_path`` need only exist here; the workbench may share no filesystem
        with us (see ``WorkbenchClient.copy_in``)."""
        self._workbench.copy_in(handle.workbench_id, host_path, workbench_path, ree_id=handle.ree_id)

    def init_ree(self, handle: ReeRoute, name: str, workbench_environment: EnvironmentBackend = "container") -> None:
        """Create the REE in the store its workbench serves; refused where one is already."""
        with self._locks(handle.ree_id):
            self._workbench.exec_simple(
                handle.workbench_id,
                ["init-ree", "--name", name, "--workbench-environment", workbench_environment],
                ree_id=handle.ree_id,
            )

    def delete_ree(self, handle: ReeRoute) -> None:
        """Delete the REE from the store its workbench serves; refused while one of its runs is active."""
        with self._locks(handle.ree_id):
            self._workbench.delete_ree(handle.workbench_id, handle.ree_id)
