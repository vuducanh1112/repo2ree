from __future__ import annotations

import json
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TextIO

from repo2ree_core.operations.capture import settle_interrupted
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.persistence.run_lock import holding_ree
from repo2ree_core.workspace.integrity import find_drift, recordable_edits
from repo2ree_protocol.command import Command, WriteScriptArgs, WriteScriptCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.layout import OVERLAY
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import (
    CommandSpanAttrs,
    record_command_status,
    record_exit_code,
    record_failure,
    record_result_boundary,
    record_result_evidence,
)

tracer = get_tracer(__name__)

_STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)


def run_session(
    cmd: Command,
    *,
    layout: ReeLayout,
    emit: LogSink,
    run_id: str | None = None,
    context: ExecutionContext | None = None,
) -> ActionResult:
    context = context or ExecutionContext.new()
    run_id = run_id or f"manual-{context.attempt_id}"
    review_id = getattr(cmd.args, "review_id", None)
    evidence: ReeLayout | ReviewLayout = layout.review(review_id) if review_id else layout
    evidence.runs.mkdir(parents=True, exist_ok=True)
    cancel_marker = layout.run_cancel_marker(run_id)
    try:
        with evidence.run_log(run_id).open("a", encoding="utf-8") as run_log, _stopped_by_signals() as stopped:

            def is_canceled() -> bool:
                return stopped.is_set() or cancel_marker.exists()

            def log(stream: str, level: str, message: str) -> None:
                emit(stream, level, message)
                _frame(run_log, run_id, {"type": "log", "stream": stream, "level": level, "message": message}, context)

            _frame(
                run_log,
                run_id,
                {
                    "type": "command",
                    "operation": str(cmd.operation),
                    "command": cmd.model_dump(mode="json"),
                    "context": context.model_dump(mode="json"),
                },
            )
            with holding_ree(layout, run_id) as holder:
                if holder is not None:
                    message = f"another command is running in this REE (run {holder}); wait for it, or cancel it"
                    log("system", "error", message)
                    result = ActionResult.failed("conflict", message)
                else:
                    result = _run_held(cmd, layout, log, run_id, is_canceled, context)
            _frame(
                run_log,
                run_id,
                {"type": "result", "operation": str(cmd.operation), "result": result.model_dump(mode="json")},
                context,
            )
            return result
    finally:
        cancel_marker.unlink(missing_ok=True)


def _run_held(
    cmd: Command,
    layout: ReeLayout,
    log: LogSink,
    run_id: str,
    is_canceled: Callable[[], bool],
    context: ExecutionContext,
) -> ActionResult:
    settle_leftover_attempts(layout, log=log)
    pick_up_authored_edits(layout, log=log, invocation=context)
    with tracer.start_as_current_span(f"session.{cmd.operation}") as span:
        CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id, execution=context).apply(span)
        result = run_command(
            cmd,
            layout=layout,
            log=log,
            run_id=run_id,
            is_canceled=is_canceled,
            context=context,
        )
        record_exit_code(span, result.exit_code)
        record_failure(span, result.failure)
        record_command_status(span, result.status)
        record_result_evidence(span, result)
        record_result_boundary(span, "session.completed", result)
    return result


def request_cancel(layout: ReeLayout, run_id: str) -> None:
    layout.runs.mkdir(parents=True, exist_ok=True)
    layout.run_cancel_marker(run_id).touch()


def settle_leftover_attempts(layout: ReeLayout, *, log: LogSink) -> list[ActionResult]:
    if not layout.manifest.is_file():
        return []
    leftovers = [record for record in read_operation_history(layout).operations if record.capture_status == "pending"]
    settled = []
    for record in leftovers:
        log("system", "warn", f"settling attempt {record.attempt_id}, which ended without reporting")
        result = settle_interrupted(layout=layout, attempt_id=record.attempt_id, log=log)
        if result is not None:
            settled.append(result)
    return settled


def pick_up_authored_edits(
    layout: ReeLayout, *, log: LogSink, invocation: ExecutionContext | None = None
) -> list[ActionResult]:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return []
    edits = recordable_edits(layout, find_drift(layout))
    if edits and store.read_ree().seal is not None:
        return []
    results: list[ActionResult] = []
    for script in edits:
        try:
            content = layout.overlay_file(script).read_bytes().decode()
        except UnicodeDecodeError:
            log("system", "warn", f"{OVERLAY}/{script} is not text, so it is not recorded")
            return results
        log("system", "info", f"recording your edit to {OVERLAY}/{script}")
        context = ExecutionContext.new(ree_id=invocation.ree_id if invocation else None)
        if invocation is not None:
            context = context.model_copy(update={"dispatch_record": invocation.dispatch_record})
        results.append(
            run_command(
                WriteScriptCommand(args=WriteScriptArgs(path=script, content=content)),
                layout=layout,
                log=log,
                run_id=f"edit-{context.attempt_id}",
                context=context,
                records_edit=script,
            )
        )
    return results


@contextmanager
def _stopped_by_signals() -> Iterator[threading.Event]:
    stopped = threading.Event()
    if threading.current_thread() is not threading.main_thread():
        yield stopped
        return
    previous = {number: signal.getsignal(number) for number in _STOP_SIGNALS}
    for number in _STOP_SIGNALS:
        signal.signal(number, lambda _signum, _frame: stopped.set())
    try:
        yield stopped
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _frame(run_log: TextIO, run_id: str, frame: dict[str, Any], context: ExecutionContext | None = None) -> None:
    run_log.write(
        json.dumps({"run_id": run_id, "context": context.model_dump(mode="json") if context else None, **frame}) + "\n"
    )
    run_log.flush()
