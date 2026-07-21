"""Handler for the remove_source operation."""

from __future__ import annotations

from repo2ree_core.envelope.handlers.source_reset import reset_source_state
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_remove_source(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "remove_source canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")

    log("system", "info", "remove_source: clearing content and resetting metadata")
    try:
        reset_source_state(layout=layout, store=store)
    except Exception as exc:
        log("system", "error", f"remove_source failed: {exc}")
        return ActionResult.failed("internal", f"remove_source failed: {exc}")

    log("system", "info", "remove_source succeeded")
    return ActionResult(status="succeeded", exit_code=0)
