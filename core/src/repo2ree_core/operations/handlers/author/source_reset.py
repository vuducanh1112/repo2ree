"""Reset source-derived REE state before acquiring a new source."""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.author import open_ree_store
from repo2ree_core.ree.store import reset_source_state
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_reset_for_source_change(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    log("system", "info", "reset_for_source_change: clearing source-derived state")
    try:
        reset_source_state(layout=layout, store=store)
    except Exception as exc:
        log("system", "error", f"reset_for_source_change failed: {exc}")
        return ActionResult.failed("internal", f"reset_for_source_change failed: {exc}")

    log("system", "info", "reset_for_source_change succeeded")
    return ActionResult(status="succeeded", exit_code=0)
