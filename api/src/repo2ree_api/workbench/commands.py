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

from repo2ree_api.deps import command_dispatcher, ree_router
from repo2ree_api.storage import author_actions
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import ReeRoute, StoreUnavailableError
from repo2ree_telemetry.bootstrap import get_meter, get_tracer
from repo2ree_telemetry.spans import CommandSpanAttrs, command_metric_attrs, record_command_status

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


def require_handle(ree_id: str) -> ReeRoute:
    """The workbench to send ``ree_id``'s commands to, or the error the author is answered with.

    404 for an REE this control plane does not know; 503 (``store_unavailable``, retryable) for
    one whose store no workbench serves at the moment.
    """
    try:
        handle = ree_router.route(ree_id)
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "store_unavailable",
                "message": f"No workbench is serving this REE's store ({exc.store_id}) right now",
                "details": {"store_id": exc.store_id},
                "retryable": True,
            },
        ) from exc
    if handle is None:
        raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")
    return handle


def dispatch_or_fail(handle: ReeRoute, cmd: Command, run_id: str, error_message: str) -> ActionResult:
    """Dispatch a single workbench command, translating failure into the error envelope.

    A handler-reported version conflict maps to 409 (retryable after re-reading);
    any other reported failure is an input or REE-state problem and maps to 400
    with the command's outputs attached so the caller can see what the workbench
    said. Transport-level failures raise WorkbenchUnavailableError instead and
    map to 503 in the app-level handler.
    """
    result = command_dispatcher.dispatch_action(handle, cmd, run_id, lambda *_: None)
    # Before any answer is decided: a failed command still names the attempt it left.
    author_actions.learn_attempt(result)
    if result.status == "succeeded":
        return result
    outputs = result.outputs or {}
    # A failed ActionResult always carries a typed Failure (enforced by the
    # ActionResult contract); read it rather than sniffing the outputs blob.
    failure = result.failure
    if failure is not None and failure.category == "conflict":
        details = {
            "expected_version": outputs.get("expected_version"),
            "actual_version": outputs.get("actual_version"),
        }
        if outputs.get("path") is not None:
            details["path"] = outputs["path"]
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "message": failure.message,
                "details": details,
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
