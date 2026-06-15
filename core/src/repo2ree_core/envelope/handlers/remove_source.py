"""Handler for the remove_source operation.

Clears upstream/, overlay/, workspace/ and snapshot.tar.gz, then resets
source fields in /ree/.workspace.json back to draft state.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers._common import utc_now
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck
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
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "remove_source: clearing content and resetting metadata")
    try:
        for subtree in (store.upstream, store.overlay, store.workspace):
            subtree.clear()
            subtree.ensure_root()
        if layout.snapshot_archive.exists():
            layout.snapshot_archive.unlink()

        meta = store.read_metadata()
        # Removing the source removes the basis for everything derived from it,
        # so reset intent to a blank slate — keeping only author metadata
        # (name and catalog_metadata) — and discard all session state.
        cleared_intent = ReeIntent(
            name=meta.ree_intent.name,
            catalog_metadata=meta.ree_intent.catalog_metadata,
        )
        updated = meta.model_copy(
            update={
                "ree_intent": cleared_intent,
                "ree_session": ReeSession(),
                "status": "draft",
                "updated_at": utc_now(),
                "external_ref": None,
            }
        )
        store.write_metadata(updated)
    except Exception as exc:
        log("system", "error", f"remove_source failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "remove_source succeeded")
    return ActionResult(status="succeeded", exit_code=0)
