"""Handler for the materialize_workspace operation.

Rebuilds /ree/workspace as the merge of /ree/upstream and /ree/overlay,
with overlay winning on conflict. Idempotent — workspace is cleared first.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.tree import copy_tree_contents
from repo2ree_core.working_environment.base import CancelCheck


def handle_materialize_workspace(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "materialize_workspace canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    log("system", "info", f"materializing {layout.workspace}")
    try:
        store.workspace.clear()
        store.workspace.ensure_root()
        if layout.upstream.is_dir():
            copy_tree_contents(layout.upstream, layout.workspace)
        if layout.overlay.is_dir():
            copy_tree_contents(layout.overlay, layout.workspace)
    except Exception as exc:
        log("system", "error", f"materialize failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "materialize_workspace succeeded")
    return ActionResult(status="succeeded", exit_code=0)
