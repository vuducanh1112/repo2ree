"""Primitives every synchronous REE command route is built from.

Three things a route needs before and around a single workbench command: resolve
the REE to a live workbench handle, wrap the work in the operation-level span and
metrics, and translate a command failure into the error envelope. They live here
rather than beside any one route because they belong to none of them — routes in
several modules compose the same three, and reaching into another route module
for them would make that module a utility hub by accident.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException

from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    command_metric_attrs,
    get_meter,
    get_tracer,
    record_command_status,
)
from repo2ree_supervisor import WorkbenchHandle

# ================================================
# Observability
# ================================================


_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_command_counter = _meter.create_counter(
    "ree.command",
    description="Number of synchronous REE commands handled, by operation and status.",
)
_command_duration = _meter.create_histogram(
    "ree.command_duration_seconds",
    description="Wall-clock duration of a synchronous REE command handler.",
    unit="s",
)


@contextmanager
def ree_command_span(operation: str, ree_id: str) -> Generator[None]:
    """Operation-level span + metrics for a synchronous REE command handler.

    Mirrors the ``run.{operation}`` root that background runs get in the run
    registry: every synchronous main command gets its own ``ree.{operation}``
    span tagged with the REE and a terminal status, plus a duration histogram
    and count, so traces and error-rate queries treat synchronous and
    background commands uniformly. The inner ``workbench.dispatch_action`` span
    nests beneath this one.

    Wrap only the command work — call ``require_handle`` first so a 404/503 for
    an unknown or unreachable REE stays out of the command's status and metrics.
    """
    t0 = time.monotonic()
    status = "succeeded"
    with _tracer.start_as_current_span(f"ree.{operation}") as span:
        CommandSpanAttrs(operation=operation, ree_id=ree_id).apply(span)
        try:
            yield
        except Exception as exc:
            status = "failed"
            span.record_exception(exc)
            raise
        finally:
            record_command_status(span, status)
            attrs = command_metric_attrs(operation, status=status)
            _command_duration.record(time.monotonic() - t0, attrs)
            _command_counter.add(1, attrs)


# ================================================
# Command dispatch
# ================================================


def require_handle(ree_id: str) -> WorkbenchHandle:
    """Return the workbench handle for ree_id or raise.

    404 if no workbench is registered for the REE; 503 if one is registered
    but its container is not currently reachable. The workbench volume is the
    single source of truth — there is no host-side fallback.
    """
    handle = workbench_manager.lookup(ree_id)
    if handle is not None:
        return handle
    if workbench_manager.is_registered(ree_id):
        raise HTTPException(status_code=503, detail="Workbench unavailable for this REE")
    raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")


def dispatch_or_fail(handle: WorkbenchHandle, cmd: Command, run_id: str, error_message: str) -> ActionResult:
    """Dispatch a single workbench command, translating failure into the error envelope.

    A handler-reported version conflict maps to 409 (retryable after re-reading);
    any other reported failure is an input or REE-state problem and maps to 400
    with the command's outputs attached so the caller can see what the workbench
    said. Transport-level failures raise WorkbenchUnavailableError instead and
    map to 503 in the app-level handler.
    """
    result = workbench_manager.dispatch_action(handle, cmd, run_id, lambda *_: None)
    if result.status == "succeeded":
        return result
    outputs = result.outputs or {}
    # A failed ActionResult always carries a typed Failure (enforced by the
    # ActionResult contract); read it rather than sniffing the outputs blob.
    failure = result.failure
    if failure is not None and failure.category == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "message": failure.message,
                "details": {
                    "path": outputs.get("path"),
                    "expected_version": outputs.get("expected_version"),
                    "actual_version": outputs.get("actual_version"),
                },
                "retryable": failure.retryable,
            },
        )
    raise HTTPException(
        status_code=400,
        detail={
            "code": f"{cmd.operation}_failed",
            "message": error_message,
            "details": {"operation": cmd.operation, "exit_code": result.exit_code, "outputs": outputs or None},
            "retryable": failure.retryable if failure is not None else False,
        },
    )
