from __future__ import annotations

import contextlib
import os
import shlex
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Literal

from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.receipt import Launched
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import (
    ExecSpanAttrs,
    record_exec_outcome,
)

tracer = get_tracer(__name__)

CancelCheck = Callable[[], bool]

CANCEL_GRACE_SECONDS = 5.0

READER_DRAIN_SECONDS = 5.0


@dataclass(frozen=True)
class StepOutcome:
    status: ActionStatus
    exit_code: int | None = None
    captured_stdout: str = field(default="")
    captured_stderr: str = field(default="")
    launched: Launched | None = None


def format_argv(argv: list[str]) -> str:
    return " ".join(shlex.quote(t) for t in argv)


def format_command(command: list[str]) -> str:
    return "$ " + format_argv(command)


@dataclass(frozen=True)
class StreamingProcessResult:
    returncode: int | None
    stdout: str
    stderr: str
    canceled: bool = False


def run_streaming_process(
    cmd: list[str],
    *,
    log: LogSink,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | str | None = None,
    is_canceled: CancelCheck = lambda: False,
) -> StreamingProcessResult:
    with tracer.start_as_current_span("process.exec") as span:
        ExecSpanAttrs(argv=format_argv(cmd), cwd=str(cwd) if cwd is not None else None).apply(span)
        result = _stream_process(cmd, log=log, stdin_text=stdin_text, env=env, cwd=cwd, is_canceled=is_canceled)
        record_exec_outcome(
            span,
            exit_code=result.returncode,
            canceled=result.canceled,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        return result


def _signal_group(proc: subprocess.Popen[str], sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, sig)


def _terminate_process_group(proc: subprocess.Popen[str], *, log: LogSink) -> None:
    _signal_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=CANCEL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        log("system", "warn", f"process group survived SIGTERM after {CANCEL_GRACE_SECONDS:g}s; sending SIGKILL")
        _signal_group(proc, signal.SIGKILL)


def _stream_process(
    cmd: list[str],
    *,
    log: LogSink,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | str | None = None,
    is_canceled: CancelCheck = lambda: False,
) -> StreamingProcessResult:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=cwd,
        start_new_session=True,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _reader(
        pipe: IO[str] | None,
        stream: Literal["stdout", "stderr"],
        level: Literal["info"],
        sink: list[str],
    ) -> None:
        if pipe is None:
            return
        for line in pipe:
            sink.append(line)
            message = line.rstrip()
            if message:
                log(stream, level, message)

    stdout_reader = threading.Thread(
        target=_reader,
        args=(proc.stdout, "stdout", "info", stdout_lines),
        daemon=True,
    )
    stderr_reader = threading.Thread(
        target=_reader,
        args=(proc.stderr, "stderr", "info", stderr_lines),
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()

    if stdin_text is not None and proc.stdin is not None:
        try:
            proc.stdin.write(stdin_text)
            proc.stdin.close()
        except BrokenPipeError:
            pass

    canceled = False
    while proc.poll() is None:
        if is_canceled():
            canceled = True
            _terminate_process_group(proc, log=log)
            break
        time.sleep(0.1)

    returncode = proc.wait()

    stdout_reader.join(timeout=READER_DRAIN_SECONDS)
    stderr_reader.join(timeout=READER_DRAIN_SECONDS)
    if stdout_reader.is_alive() or stderr_reader.is_alive():
        log(
            "system",
            "warn",
            f"output readers still draining after {READER_DRAIN_SECONDS:g}s "
            "(a child still holds the pipe); captured output may be truncated",
        )

    return StreamingProcessResult(
        returncode=returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        canceled=canceled,
    )
