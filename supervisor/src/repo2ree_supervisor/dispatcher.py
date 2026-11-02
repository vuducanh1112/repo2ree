"""Typed commands and queries sent to the workbench an REE is served by.

The dispatcher consumes the workbench's ``Frame`` stream, forwards log and span frames as they
arrive, journals each dispatch exchange, and returns the terminal result frame's ``ActionResult``.
It never sets up or tears down a workbench; it is told, through ``on_unavailable``, to let whoever
does know that one stopped answering.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from typing import Any

from repo2ree_protocol.command import Command
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ErrorFrame, LogFrame, LogSink, ResultFrame, SpanFrame, UnavailableFrame
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
from repo2ree_supervisor.client import WorkbenchClient, WorkbenchUnavailableError
from repo2ree_supervisor.handle import WorkbenchHandle
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

__all__ = ["CommandDispatcher"]

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
        on_unavailable: Callable[[WorkbenchHandle], object] | None = None,
    ) -> None:
        self._workbench = workbench
        self._locks = locks
        self._span_sink = span_sink
        self._on_unavailable = on_unavailable or (lambda handle: None)

    # ------------------------------------------------
    # Action dispatch
    # ------------------------------------------------

    def dispatch_action(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
        context: ExecutionContext | None = None,
    ) -> ActionResult:
        """Run a typed Command inside the workbench; stream logs to log."""
        context = context or ExecutionContext.new(ree_id=handle.ree_id)
        if context.ree_id not in {None, handle.ree_id}:
            raise ValueError("Execution context belongs to another REE")
        context = context.model_copy(update={"ree_id": handle.ree_id})
        with tracer.start_as_current_span("workbench.dispatch_action") as span:
            CommandSpanAttrs(
                operation=str(cmd.operation), run_id=run_id, ree_id=handle.ree_id, execution=context
            ).apply(span)
            WorkbenchSpanAttrs(
                workbench_id=handle.workbench_id,
            ).apply(span)
            # The whole command as dispatched — envelope and args — recorded
            # before it runs, for the reason core's own dispatch records its
            # inputs first: a command that is killed or times out still carries
            # what it was asked to do. Without this the span reports only what
            # came back, which is half a wide event.
            #
            # Namespaced ``cmd`` rather than ``arg`` because it is the whole
            # envelope, not the argument object a handler receives; core's
            # ``repo2ree.arg.*`` remains the inner view of the same call.
            record_span_facts(span, cmd.model_dump(), namespace="cmd")
            # Time spent blocked here is per-REE lock contention (another run in
            # progress); record it on acquisition so wait is a first-class metric
            # rather than something inferred from the dispatch/execute span gap.
            _lock_t0 = time.monotonic()
            with self._locks(handle.ree_id):
                _lock_wait_duration.record(
                    time.monotonic() - _lock_t0,
                    command_metric_attrs(str(cmd.operation)),
                )
                with tracer.start_as_current_span("workbench.execute"):
                    _t0 = time.monotonic()
                    try:
                        result, context = self._dispatch_recorded(handle, cmd, run_id, log, context)
                    except WorkbenchUnavailableError:
                        self._on_unavailable(handle)
                        raise
                    _exec_duration.record(
                        time.monotonic() - _t0,
                        command_metric_attrs(str(cmd.operation), status=result.status),
                    )
            if result.context is not None and result.context != context:
                raise RuntimeError("Executor returned a different execution context")
            if result.history is not None and result.history.attempt_id != context.attempt_id:
                raise RuntimeError("Executor returned history for a different execution attempt")
            result = result.model_copy(update={"context": context})
            # Mirror the executor's wide event host-side: the command span's
            # outputs travel over the best-effort span relay, so this dispatch
            # span is the copy guaranteed to reach the collector.
            record_exit_code(span, result.exit_code)
            record_span_facts(span, result.outputs, namespace="output")
            record_failure(span, result.failure)
            record_command_status(span, result.status)
            record_result_evidence(span, result)
            record_result_boundary(span, "supervisor.received", result)
            return result

    def cancel_run(self, handle: WorkbenchHandle, run_id: str) -> None:
        """Ask the workbench executor to stop a running action.

        This deliberately does not take the per-REE dispatch lock: the command we
        are canceling is usually the one holding that lock.
        """
        self._workbench.cancel_run(handle.workbench_id, run_id, ree_id=handle.ree_id)

    def _dispatch_recorded(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
        context: ExecutionContext,
    ) -> tuple[ActionResult, ExecutionContext]:
        """One ``dispatch`` exchange: the request is journaled before it leaves, and one outcome after.

        Every terminal frame is recorded as received, so a duplicated result is
        visible to the checker rather than silently overwritten here. The two
        sides cite each other: the command carries the request's journal
        reference into the attempt's record, and the recorded result names the
        commit that captured the attempt. Returns the result and the context sent.
        """
        dispatched = events.dispatch_sent(
            context.attempt_id, partition=handle.ree_id, facts={"operation": str(cmd.operation), "run_id": run_id}
        )
        context = context.model_copy(update={"dispatch_record": dispatched})
        answered = False

        def observe(message: events.DispatchResponse, facts: events.ResultFacts | None = None) -> None:
            nonlocal answered
            answered = True
            events.dispatch_received(context.attempt_id, message, partition=handle.ree_id, facts=facts)

        try:
            result = self._dispatch_action_locked(handle, cmd, run_id, log, context, observe)
        except BaseException as exc:
            if not answered:
                events.dispatch_abandoned(context.attempt_id, partition=handle.ree_id, reason=type(exc).__name__)
            raise
        if not answered:
            events.dispatch_abandoned(context.attempt_id, partition=handle.ree_id, reason="closed_without_response")
        return result, context

    def _dispatch_action_locked(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
        context: ExecutionContext,
        observe: Callable[[events.DispatchResponse, events.ResultFacts | None], None],
    ) -> ActionResult:
        cmd_json = cmd.model_dump_json()

        # No TRACEPARENT here on purpose. The workbench injects it at the hop that
        # actually spawns the executor, so a context set from this span would be
        # overwritten one layer down — two propagation points with the later
        # silently winning. What this span does own is asking for the relay:
        # when the API injected a span_sink the executor should stream its spans
        # back over stderr, having no path to the collector itself.
        env: dict[str, str] = {}
        if self._span_sink is not None:
            env["TRACE_RELAY"] = "1"

        # Consume the workbench's frame stream live: forward log frames to the sink
        # and relayed span frames to the span_sink as they arrive (not buffered to
        # the end) so a command that hangs or gets killed still ships what it
        # emitted before stalling — the case a trace is most useful. The span_sink
        # is non-blocking (it enqueues for a background forwarder), so export never
        # sits on this loop, the per-REE lock, or the measured execute window.
        result: ActionResult | None = None
        for frame in self._workbench.exec_action(
            handle.workbench_id, cmd_json, run_id, env, context, ree_id=handle.ree_id
        ):
            if isinstance(frame, LogFrame):
                log(frame.stream, frame.level, frame.message)
            elif isinstance(frame, SpanFrame):
                if self._span_sink is not None:
                    self._span_sink([frame.payload])
            elif isinstance(frame, ResultFrame):
                history = frame.result.history
                observe(
                    "result",
                    {
                        "status": frame.result.status,
                        "commit": history.after_snapshot_id if history else None,
                        "record": history.record_digest if history else None,
                    },
                )
                result = frame.result
            elif isinstance(frame, UnavailableFrame):
                observe("unavailable", None)
                _container_gone_counter.add(1, command_metric_attrs(str(cmd.operation)))
                raise WorkbenchUnavailableError(frame.detail)
            elif isinstance(frame, ErrorFrame):
                observe("error", None)
                raise RuntimeError(frame.detail)

        if result is None:
            # Stream ended without a terminal result frame: the executor exited
            # or the connection dropped before reporting an outcome.
            return ActionResult.failed(
                "internal",
                f"{cmd.operation} ended without a result",
                origin="supervisor",
                retryable=True,
            )
        return result

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30) -> bytes:
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
        self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30
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

    def _query_json(self, handle: WorkbenchHandle, *argv: str) -> dict[str, Any]:
        """Run a read-only CLI subcommand and parse its stdout as a JSON object.

        The one place the workbench's untyped JSON becomes a typed value, so the
        ``Any`` that ``json.loads`` returns is narrowed once rather than at each
        of the five call sites below.
        """
        parsed: dict[str, Any] = json.loads(self.dispatch_query(handle, *argv))
        return parsed

    def get_ree_manifest(self, handle: WorkbenchHandle) -> Ree:
        return Ree.model_validate(self._query_json(handle, GET_REE_MANIFEST))

    def get_ree_document(self, handle: WorkbenchHandle) -> WorkbenchReeDocument:
        return WorkbenchReeDocument.model_validate(self._query_json(handle, GET_REE_DOCUMENT))

    def get_ree_state(self, handle: WorkbenchHandle) -> WorkbenchReeDocument:
        """Return composed REE state without embedding text file contents."""
        return WorkbenchReeDocument.model_validate(self._query_json(handle, GET_REE_DOCUMENT, GET_REE_DOCUMENT_SUMMARY))

    def get_history(self, handle: WorkbenchHandle) -> OperationHistory:
        return OperationHistory.model_validate(self._query_json(handle, GET_HISTORY))

    def get_reviews(self, handle: WorkbenchHandle) -> ReviewSet:
        return ReviewSet.model_validate(self._query_json(handle, GET_REVIEWS))

    def read_ree_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        # REE files can include large runtime and result artifacts.
        return self.dispatch_query(handle, READ_REE_FILE, READ_REE_FILE_PATH, path, timeout=120)

    def build_archive(self, handle: WorkbenchHandle) -> ReceivedFile:
        """The REE's archive as a file on the control plane; the caller removes it.

        Built and uploaded beside the control socket (``exec_upload``), under the
        per-REE lock, which is released once the file has arrived — never held for
        as long as a client takes to download it. Zipping and sending scale with
        the REE's size, hence the generous timeout."""
        with self._locks(handle.ree_id):
            return self._workbench.exec_upload(handle.workbench_id, [BUILD_ARCHIVE], timeout=600, ree_id=handle.ree_id)

    def copy_to_workbench(self, handle: WorkbenchHandle, host_path: str, workbench_path: str) -> None:
        """Copy a control-plane-local file into the workbench.

        ``host_path`` need only exist here; the workbench may share no filesystem
        with us (see ``WorkbenchClient.copy_in``)."""
        self._workbench.copy_in(handle.workbench_id, host_path, workbench_path, ree_id=handle.ree_id)

    def init_ree(self, handle: WorkbenchHandle, name: str) -> None:
        """Create the REE in the store its workbench serves; refused where one is already."""
        with self._locks(handle.ree_id):
            self._workbench.exec_simple(handle.workbench_id, ["init-ree", "--name", name], ree_id=handle.ree_id)

    def delete_ree(self, handle: WorkbenchHandle) -> None:
        """Delete the REE from the store its workbench serves; refused while one of its runs is active."""
        with self._locks(handle.ree_id):
            self._workbench.delete_ree(handle.workbench_id, handle.ree_id)
