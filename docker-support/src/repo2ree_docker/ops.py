"""Shared Docker operation plumbing: metrics, spans, and CLI wrappers.

Kept out of the provider so the "Docker support has no process authority"
import contract can hold: every Docker call is timed and traced the same way
here, and nothing in this package decides what to provision.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager

from repo2ree_docker import cli as docker_cli
from repo2ree_docker.errors import WorkbenchGoneError
from repo2ree_protocol.tracing import command_metric_attrs, get_meter, get_tracer, record_command_status

tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_docker_operation_duration = _meter.create_histogram(
    "workbench.docker_operation_duration_seconds",
    description="Wall-clock duration of Docker CLI operations performed by the workbench.",
    unit="s",
)
_docker_operation_counter = _meter.create_counter(
    "workbench.docker_operation",
    description="Number of Docker CLI operations performed by the workbench.",
)
_workbench_gone_counter = _meter.create_counter(
    "workbench.workbench_gone",
    description="Number of Docker operations that found the target workbench gone or stopping.",
)


class ContainerStateUnknownError(RuntimeError):
    """`docker inspect` could not determine the container's state.

    Distinct from "container is not running": a timed-out or errored probe means
    the daemon was momentarily unreachable, not that the bench is gone. Callers
    must not treat this as a confirmed-down signal (which would fail a healthy
    session's next action with a spurious "workbench unavailable").
    """


class DockerOp:
    """Mutable status holder for an in-flight docker operation.

    The body may override ``status`` for an outcome the exception mapping can't
    infer (a result carrying its own status, or a probe that swallows an
    indeterminate result and returns a default)."""

    __slots__ = ("status",)

    def __init__(self) -> None:
        self.status = "succeeded"


@contextmanager
def docker_op(operation: str) -> Generator[DockerOp]:
    """Time a docker operation and record its metric exactly once, with the
    right terminal status on every exit path.

    Status defaults to ``"succeeded"``; a raised exception maps to
    ``"unavailable"`` (workbench gone), ``"unknown"`` (an indeterminate probe)
    or ``"failed"`` unless the body set one explicitly. It catches
    ``Exception``, not ``BaseException``, so an abandoned generator
    (``GeneratorExit``) or cancellation is not recorded as a failure."""
    started_at = time.monotonic()
    op = DockerOp()
    try:
        yield op
    except WorkbenchGoneError:
        op.status = "unavailable"
        raise
    except ContainerStateUnknownError:
        op.status = "unknown"
        raise
    except Exception:
        op.status = "failed"
        raise
    finally:
        record_docker_operation(operation, started_at, op.status)


def record_docker_operation(operation: str, started_at: float, status: str) -> None:
    attrs = command_metric_attrs(operation, status=status)
    _docker_operation_counter.add(1, attrs)
    _docker_operation_duration.record(time.monotonic() - started_at, attrs)
    if status == "unavailable":
        _workbench_gone_counter.add(1, command_metric_attrs(operation))
    # Docker CLI calls also become spans, so a slow provision breaks down into
    # its pulls/copies/runs in the trace. Higher-level operations (provision,
    # exec_action, …) are excluded — the workbench.request span already covers
    # them, and a duplicate sibling would only clutter the waterfall.
    if operation.startswith("docker."):
        _emit_docker_span(operation, started_at, status)


def _emit_docker_span(operation: str, started_at: float, status: str) -> None:
    """Mint a completed span for a docker CLI call, with explicit timestamps.

    The helpers already time themselves for the duration metric, so instead of
    wrapping every call site (several are generators) the span is created
    retroactively at completion: started against the current context — nesting
    under the in-flight ``workbench.request`` — and ended at the real boundaries.
    """
    end_ns = time.time_ns()
    start_ns = end_ns - int((time.monotonic() - started_at) * 1_000_000_000)
    span = tracer.start_span(operation, start_time=start_ns)
    record_command_status(span, status)
    span.end(end_time=end_ns)


def run_docker(*args: str, timeout: int = 60) -> None:
    """Run a docker subcommand, raising on a non-zero exit."""
    run_docker_out(*args, timeout=timeout)


def run_docker_out(*args: str, timeout: int = 60) -> str:
    """Like :func:`run_docker` but returns stripped stdout (e.g. a created container id)."""
    with docker_op(f"docker.{args[0]}"):
        return docker_cli.docker_out(args, timeout)


def run_docker_silent(*args: str) -> None:
    """Like :func:`run_docker` but ignores failures (for cleanup paths)."""
    with docker_op(f"docker.{args[0]}") as op:
        try:
            result = subprocess.run(["docker", *args], check=False, capture_output=True, timeout=30)
            if result.returncode != 0:
                op.status = "failed_ignored"
        except (subprocess.SubprocessError, OSError):
            op.status = "failed_ignored"


def run_docker_remove(*args: str) -> None:
    """Idempotent but strict cleanup for acknowledged user deletion."""
    with docker_op(f"docker.{args[0]}"):
        result = subprocess.run(["docker", *args], check=False, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return
        detail = docker_cli.failure_detail(result.stderr, result.stdout)
        if "No such container" in detail or "No such volume" in detail:
            return
        raise RuntimeError(f"docker {args[0]} failed: {detail}")


def container_running(container_name: str) -> bool:
    """True iff the container is *confirmed* running.

    Raises :class:`ContainerStateUnknownError` when the probe itself could not run —
    a timeout or a non-"not-found" docker error — so a transient daemon hiccup
    is never silently reported as "not running".
    """
    with docker_op("docker.inspect"):
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerStateUnknownError(f"docker inspect timed out for {container_name}") from exc
        if result.returncode == 0:
            return result.stdout.strip() == "true"
        # A genuinely absent container is a confirmed "not running"; any other
        # failure (daemon unreachable, permission blip) is indeterminate.
        stderr = result.stderr.lower()
        if "no such object" in stderr or "no such container" in stderr:
            return False
        raise ContainerStateUnknownError(
            f"docker inspect failed for {container_name}: {docker_cli.failure_detail(result.stderr, result.stdout)}"
        )
