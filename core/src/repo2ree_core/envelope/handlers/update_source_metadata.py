"""Handler for the update_source_metadata operation.

Updates /ree/.workspace.json after a successful source acquisition:
sets status=ready and records acquisition facts in reeIntent and reeSession.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.envelope.handlers._common import utc_now
from repo2ree_core.storage.layout import SNAPSHOT_FILENAME, ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck
from repo2ree_protocol.command import UpdateSourceMetadataArgs
from repo2ree_protocol.result import ActionResult


def handle_update_source_metadata(
    args: UpdateSourceMetadataArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "update_source_metadata canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "updating source metadata")
    try:
        meta = store.read_metadata()
        ts = utc_now()

        if args.mode == "download":
            intent = meta.ree_intent.model_copy(update={"origin_url": args.origin_url, "source_type": args.source_type})
            session = meta.ree_session.with_source(
                acquired_by="download",
                snapshot_archive=SNAPSHOT_FILENAME,
                snapshot_captured_at=ts,
                resolved_commit=args.resolved_commit or None,
            )
        else:
            intent = meta.ree_intent
            session = meta.ree_session.with_source(
                acquired_by="upload",
                archive_name=args.archive_name,
                snapshot_archive=SNAPSHOT_FILENAME,
                snapshot_captured_at=ts,
            )

        updated = meta.model_copy(
            update={
                "ree_intent": intent,
                "ree_session": session,
                "status": "ready",
                "updated_at": ts,
                "external_ref": intent.origin_url or None,
            }
        )
        store.write_metadata(updated)
    except Exception as exc:
        log("system", "error", f"metadata update failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "update_source_metadata succeeded")
    return ActionResult(status="succeeded", exit_code=0)
