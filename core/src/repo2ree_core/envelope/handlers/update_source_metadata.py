"""Handler for the update_source_metadata operation.

Updates /ree/.workspace.json after a successful source acquisition:
sets status=ready and records acquisition facts in reeIntent and reeSession.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.container.run_script import CancelCheck, LogSink
from repo2ree_core.source_repo import directory_swhid, resolved_git_head
from repo2ree_core.storage.layout import SNAPSHOT_FILENAME, ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.command import UpdateSourceMetadataArgs
from repo2ree_protocol.result import ActionResult


def _compute_source_swhid(upstream: Path, log: LogSink) -> str:
    """Best-effort ``swh:1:dir:`` identifier of the acquired source tree.

    Returns ``""`` (and logs a warning) on any failure: a missing tree or a
    hashing error must not block marking the workspace ready.
    """
    try:
        return directory_swhid(upstream)
    except Exception as exc:
        log("system", "warn", f"swhid computation skipped: {exc}")
        return ""


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

        # Stamp the computed identifier only when we got one, so a hashing
        # failure never clobbers a swhid already on the intent.
        swhid = _compute_source_swhid(layout.upstream, log)
        swhid_update = {"swhid": swhid} if swhid else {}
        if swhid:
            log("system", "info", f"source swhid: {swhid}")

        if args.mode == "download":
            # Settle the concrete commit onto the intent (like swhid) so the seal
            # can pin a re-fetch; only meaningful for git sources. Read HEAD from
            # the acquired tree — empty when it carries no git history.
            revision = resolved_git_head(layout.upstream) if args.source_type == "git" else ""
            revision_update = {"revision": revision} if revision else {}
            if revision:
                log("system", "info", f"source revision: {revision}")
            intent = meta.ree_intent.model_copy(
                update={
                    "origin_url": args.origin_url,
                    "source_type": args.source_type,
                    **revision_update,
                    **swhid_update,
                }
            )
            session = meta.ree_session.with_source(
                acquired_by="download",
                snapshot_archive=SNAPSHOT_FILENAME,
                snapshot_captured_at=ts,
                resolved_commit=revision or None,
            )
        else:
            intent = meta.ree_intent.model_copy(update=swhid_update)
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
