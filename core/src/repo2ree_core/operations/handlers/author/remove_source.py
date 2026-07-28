"""Handler for the remove_source operation."""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import open_ree_store
from repo2ree_core.ree.store import reset_source_state
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_remove_source(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    log("system", "info", "remove_source: clearing content and resetting metadata")
    try:
        reset_source_state(layout=layout, store=store)
    except Exception as exc:
        log("system", "error", f"remove_source failed: {exc}")
        return failed_from_exception(exc, f"remove_source failed: {exc}")

    log("system", "info", "remove_source succeeded")
    return ActionResult(status="succeeded", exit_code=0)
