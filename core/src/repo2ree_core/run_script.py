"""Generic streaming subprocess runner and the workspace-script execution path.

Containers are the author's concern, not this module's: each runnable owns an
overlay script that enters its runtime itself (e.g. its own ``docker run``),
and this module just executes such scripts as plain subprocesses with streamed
logs and cooperative cancellation.
"""

from __future__ import annotations

import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from repo2ree_core.path_safety import resolve_within
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_protocol.tracing import (
    ExecSpanAttrs,
    ScriptSpanAttrs,
    get_tracer,
    record_command_status,
    record_exec_outcome,
    record_span_facts,
)

tracer = get_tracer(__name__)

CancelCheck = Callable[[], bool]  # True once a cancel has been requested


@dataclass(frozen=True)
class StepOutcome:
    """Result of a single lifecycle-script execution."""

    status: ActionStatus
    exit_code: int | None = None
    captured_stdout: str = field(default="")
    captured_stderr: str = field(default="")


# ================================================
# Command formatting and output streaming
# ================================================


def format_argv(argv: list[str]) -> str:
    """Render an argv list as a single, copy-pasteable shell line."""
    return " ".join(shlex.quote(t) for t in argv)


def format_command(command: list[str]) -> str:
    return "$ " + format_argv(command)


def stream_output(log: LogSink, result: subprocess.CompletedProcess[str]) -> None:
    for line in (result.stdout or "").splitlines():
        if line.strip():
            log("stdout", "info", line)
    for line in (result.stderr or "").splitlines():
        if line.strip():
            log("stderr", "warn", line)


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
    is_canceled=lambda: False,
) -> StreamingProcessResult:
    """Run *cmd*, streaming child output while preserving captured streams.

    Each invocation is one ``workbench.exec`` span carrying the argv, exit
    code, output sizes, and — on failure — the output tails, so what happened
    inside the workbench survives the container itself.
    """
    with tracer.start_as_current_span("workbench.exec") as span:
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


def _stream_process(
    cmd: list[str],
    *,
    log: LogSink,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | str | None = None,
    is_canceled=lambda: False,
) -> StreamingProcessResult:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=cwd,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _reader(
        pipe,
        stream: Literal["stdout", "stderr"],
        level: Literal["info", "warn"],
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
        args=(proc.stderr, "stderr", "warn", stderr_lines),
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
            proc.terminate()
            break
        time.sleep(0.1)

    try:
        returncode = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        returncode = proc.wait()

    stdout_reader.join(timeout=5)
    stderr_reader.join(timeout=5)

    return StreamingProcessResult(
        returncode=returncode,
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        canceled=canceled,
    )


def run_workspace_script(
    workspace: Path,
    script_rel: str,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
) -> StepOutcome:
    """Run a workspace-relative script under ``sh`` from the workspace root.

    The single execution path shared by the lifecycle runner
    (``experiment/run.py``) and the build/activation handlers: the workbench IS
    the isolated environment, so the script runs as a native subprocess with no
    nested container. Running from the workspace root lets authors reference
    project files by their workspace-relative paths regardless of where REE keeps
    its own scripts; wrapper scripts are POSIX ``sh`` while project scripts that
    need bash or their own directory (e.g. ``docker build .``) invoke it
    explicitly. Scripts that resolve outside the workspace are rejected.
    """
    workspace = workspace.resolve()
    with tracer.start_as_current_span("workbench.run_script") as span:
        ScriptSpanAttrs(path=script_rel).apply(span)
        script_abs = resolve_within(workspace, script_rel)
        if script_abs is None:
            log("system", "error", f"script escapes workspace: {script_rel}")
            record_span_facts(span, {"script.error": "escapes workspace"})
            return StepOutcome("failed", 1)
        if not script_abs.is_file():
            log("system", "error", f"script not found: {script_rel}")
            record_span_facts(span, {"script.error": "not found"})
            return StepOutcome("failed", 1)

        cmd = ["sh", script_rel]
        log("system", "info", f"$ {format_argv(cmd)}")

        result = run_streaming_process(cmd, log=log, cwd=workspace, is_canceled=is_canceled)

        if result.canceled or is_canceled():
            status: ActionStatus = "canceled"
        else:
            status = "succeeded" if result.returncode == 0 else "failed"
        record_command_status(span, status)
        return StepOutcome(status, result.returncode, result.stdout, result.stderr)
