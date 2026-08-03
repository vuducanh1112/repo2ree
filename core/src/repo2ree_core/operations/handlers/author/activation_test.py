"""Run the REE's dedicated activation test against current evidence."""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers.author.runnable import handle_runnable_operation
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_activation_test(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    return handle_runnable_operation(
        "test_activation",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
