"""One command run against an REE, as every caller runs it: a person at a terminal, or a workbench.

The session keeps the command's run log (``runs/<run_id>.ndjson``: the command, every log line, the result) and
stops it cooperatively on SIGTERM, SIGINT or the run's cancel marker. Before the command starts, it settles any
attempt a process that ended without reporting left behind, and records the scripts the author edited in place.
What the caller sees of the run is its own ``emit``; the run log is the record.
"""

from __future__ import annotations

import json
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TextIO

from repo2ree_core.execution.runners import ScriptRunner
from repo2ree_core.operations.capture import settle_interrupted
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_protocol.command import Command, WriteFileArgs, WriteFileCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.reserved_paths import is_overlay_path
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import (
    CommandSpanAttrs,
    attach_remote_context,
    detach_context,
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
    runner: ScriptRunner,
    emit: LogSink,
    run_id: str | None = None,
    context: ExecutionContext | None = None,
    traceparent: str | None = None,
) -> ActionResult:
    """Run ``cmd`` against the REE at ``layout``, logging to ``emit`` and to the run log, and return its result."""
    context = context or ExecutionContext.new()
    run_id = run_id or f"manual-{context.attempt_id}"
    # Review commands keep their logs in their own attempt namespace, so reviewer evidence never lands in the
    # author's runs/. Recognised by the arg they all carry, so a new review step needs no branch here.
    review_id = getattr(cmd.args, "review_id", None)
    evidence: ReeLayout | ReviewLayout = layout.review(review_id) if review_id else layout
    evidence.runs.mkdir(parents=True, exist_ok=True)
    cancel_marker = layout.run_cancel_marker(run_id)
    token = attach_remote_context(traceparent)
    try:
        with evidence.run_log(run_id).open("a", encoding="utf-8") as run_log, _stopped_by_signals() as stopped:

            def is_canceled() -> bool:
                return stopped.is_set() or cancel_marker.exists()

            def log(stream: str, level: str, message: str) -> None:
                emit(stream, level, message)
                _frame(run_log, run_id, {"type": "log", "stream": stream, "level": level, "message": message}, context)

            # The command as it arrived, whole; with the result frame below, the complete contract of one
            # operation, joined to its span and to the receipt it files by run_id.
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
            settle_leftover_attempts(layout, log=log)
            pick_up_authored_edits(layout, runner=runner, log=log)
            # The process itself, as one span, so a trace shows the process boundary between whoever started
            # it and core's command span.
            with tracer.start_as_current_span(f"executor.{cmd.operation}") as span:
                CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id, execution=context).apply(span)
                result = run_command(
                    cmd,
                    layout=layout,
                    runner=runner,
                    log=log,
                    run_id=run_id,
                    is_canceled=is_canceled,
                    context=context,
                )
                record_exit_code(span, result.exit_code)
                record_failure(span, result.failure)
                record_command_status(span, result.status)
                record_result_evidence(span, result)
                record_result_boundary(span, "executor.completed", result)
            _frame(
                run_log,
                run_id,
                {"type": "result", "operation": str(cmd.operation), "result": result.model_dump(mode="json")},
                context,
            )
            return result
    finally:
        detach_context(token)
        # Each run clears its own marker, so a stale one never cancels a later run that reuses the id.
        cancel_marker.unlink(missing_ok=True)


def request_cancel(layout: ReeLayout, run_id: str) -> None:
    """Ask the run ``run_id`` in this REE to stop: it rolls the REE back and captures its attempt as canceled."""
    layout.runs.mkdir(parents=True, exist_ok=True)
    layout.run_cancel_marker(run_id).touch()


def settle_leftover_attempts(layout: ReeLayout, *, log: LogSink) -> list[ActionResult]:
    """Settle every attempt a process began in this REE and never reported on, before anything else runs.

    An attempt still running holds the REE's history lock, which settling takes too, so a live one is waited
    for and then answers as it settled; only an attempt whose process is gone is rolled back.
    """
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


def pick_up_authored_edits(layout: ReeLayout, *, runner: ScriptRunner, log: LogSink) -> list[ActionResult]:
    """Record every script the author edited in ``overlay/`` directly, before anything else runs.

    The overlay is where an REE's scripts live, and a person edits them there with their own editor; until an
    edit is written through ``write_file`` the workspace keeps the old script and the definition its old digest.
    Each edited script is written as it is, an attempt of its own, so its history is that of an edit made through
    any other caller. A script deleted from the overlay directly is not picked up: ``ree rm`` deletes one.
    """
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return []
    edited = [
        path
        for path in store.overlay.iter_files()
        if is_overlay_path(str(path))
        and (not store.workspace.is_file(path) or store.workspace.read_bytes(path) != store.overlay.read_bytes(path))
    ]
    if edited and store.read_ree().seal is not None:
        log("system", "warn", f"a sealed REE takes no edits; not picked up: {', '.join(map(str, edited))}")
        return []
    results = []
    for path in edited:
        try:
            content = store.overlay.read_bytes(path).decode()
        except UnicodeDecodeError:
            log("system", "warn", f"{path} is not text, so it is not picked up")
            continue
        log("system", "info", f"picking up the edit to {path}")
        context = ExecutionContext.new()
        results.append(
            run_command(
                WriteFileCommand(args=WriteFileArgs(path=str(path), content=content)),
                layout=layout,
                runner=runner,
                log=log,
                run_id=f"edit-{context.attempt_id}",
                context=context,
            )
        )
    return results


@contextmanager
def _stopped_by_signals() -> Iterator[threading.Event]:
    """SIGTERM and SIGINT ask for the same cooperative stop as the cancel marker: the script is stopped, the REE
    rolled back, and the attempt captured, not abandoned. Only the main thread can take signals."""
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
    """Append one self-describing NDJSON frame: it names its ``type`` and its run, so a reader filters lines
    without tracking position or file names."""
    run_log.write(
        json.dumps({"run_id": run_id, "context": context.model_dump(mode="json") if context else None, **frame}) + "\n"
    )
    run_log.flush()
