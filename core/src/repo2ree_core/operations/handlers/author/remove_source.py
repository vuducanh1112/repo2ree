"""Handler for the remove_source operation.

The retraction half of the source lifecycle, and now its only one: acquiring
refuses into an occupied slot rather than clearing it, so this is the single
way an REE gives its source up. It is also the recovery for an acquisition
killed mid-effect, which leaves content on disk that the state never recorded.

Note that ``reset_source_state`` is broader than its caller's name: it also
clears ``overlay/`` (authored files) and the selected author receipts, and
resets the intent to its identity fields. That breadth predates this split and
is deliberately unchanged here — whether changing a source should discard
authored build scripts is a product decision, not a consequence of where the
reset is called from.
"""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import open_ree_store
from repo2ree_core.persistence.directory import reset_source_state
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
