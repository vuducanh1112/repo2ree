"""Generic streaming subprocess runner and the workspace-script execution path.

Containers are the author's concern, not this module's: each runnable owns an
overlay script that enters its runtime itself (e.g. its own ``docker run``),
and this module just executes such scripts as plain subprocesses with streamed
logs and cooperative cancellation.
"""

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

# Grace period between asking a canceled process group to stop (SIGTERM) and
# forcing it (SIGKILL). Cooperative shutdown gets a real window; a shell that
# ignores SIGTERM, or a child that outlives its parent, is killed after it.
CANCEL_GRACE_SECONDS = 5.0

# How long to wait for the output readers to drain after the process exits. A
# grandchild that inherited the pipe can hold it open past its parent's exit,
# and waiting on that indefinitely would hang the command; what is bounded here
# is the wait, not the truncation it implies — see _stream_process.
READER_DRAIN_SECONDS = 5.0


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


def _signal_group(proc: subprocess.Popen[str], sig: int) -> None:
    """Send *sig* to the process group led by *proc*.

    ``proc`` is its own group leader (``start_new_session``), so its pid is the
    pgid and the signal reaches every descendant. A missing group — the tree
    already exited between the poll and here — is not an error.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, sig)


def _terminate_process_group(proc: subprocess.Popen[str], *, log: LogSink) -> None:
    """Stop a canceled process tree: SIGTERM, then SIGKILL after a deadline.

    The group gets ``CANCEL_GRACE_SECONDS`` to exit cooperatively; anything
    still alive after that — a shell ignoring SIGTERM, a child that outlived its
    parent — is force-killed so cancellation cannot leave the tree running.
    """
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
        # Put the shell in its own session/process group so a cancel can signal
        # the whole tree — children and grandchildren the script spawned — not
        # just the immediate shell, which would leave them orphaned. A new
        # session also means we never signal the executor that launched us.
        start_new_session=True,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def _reader(
        pipe: IO[str] | None,
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
            _terminate_process_group(proc, log=log)
            break
        time.sleep(0.1)

    returncode = proc.wait()

    stdout_reader.join(timeout=READER_DRAIN_SECONDS)
    stderr_reader.join(timeout=READER_DRAIN_SECONDS)
    if stdout_reader.is_alive() or stderr_reader.is_alive():
        # Say so rather than return quietly short. Everything downstream — the
        # run log, the receipt, the failure tails on the span — is built from
        # these buffers, and silence in a run log reads as "the script printed
        # nothing more", which is the one thing that is not true here.
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
