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


def require_handle(ree_id: str) -> ReeRoute:
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
    result = command_dispatcher.dispatch_action(handle, cmd, run_id, lambda *_: None)
    author_actions.learn_attempt(result)
    if result.status == "succeeded":
        return result
    outputs = result.outputs or {}
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
            "message": failure.message if failure is not None else error_message,
            "details": {"operation": cmd.operation, "exit_code": result.exit_code, "outputs": outputs or None},
            "retryable": failure.retryable if failure is not None else False,
        },
    )
