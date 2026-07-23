"""Reset source-derived REE state before acquiring a new source."""

from __future__ import annotations

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers._common import open_ree_store
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def reset_source_state(*, layout: ReeLayout, store: ReeStore) -> None:
    """Clear source-derived state while preserving REE identity metadata.

    Upload staging and run logs are intentionally left alone: staging is the
    handoff into the source pipeline, and logs are operational history.
    """
    for subtree in (store.upstream, store.overlay, store.artifacts, store.workspace):
        subtree.clear()
        subtree.ensure_root()
    store.ensure_reserved_overlay_scripts()

    for path in (
        layout.snapshot_archive,
        layout.acquire_script,
        layout.materialize_script,
        layout.manifest,
        layout.sealed_archive,
    ):
        path.unlink(missing_ok=True)

    meta = store.read_metadata()
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


def handle_reset_for_source_change(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "reset_for_source_change canceled before start")
        return ActionResult(status="canceled")

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
