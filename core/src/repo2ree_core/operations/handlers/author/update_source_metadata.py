"""Handler for the update_source_metadata operation.

Updates /ree/.workspace.json after a successful source acquisition:
sets status=ready and records acquisition facts in reeIntent and reeSession.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.domain.primitives import GitRevision, ReePath, Swhid, format_utc_instant
from repo2ree_core.domain.ree.transitions import record_source_acquisition
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import open_ree_store
from repo2ree_core.persistence.layout import SNAPSHOT_FILENAME
from repo2ree_core.persistence.repository import load_ree
from repo2ree_core.source_repo import directory_swhid, resolved_git_head
from repo2ree_core.time_utils import utc_now_instant
from repo2ree_protocol.command import UpdateSourceMetadataArgs
from repo2ree_protocol.log import LogSink
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
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    log("system", "info", "updating source metadata")
    try:
        meta = store.read_metadata()
        ree = load_ree(layout, store, metadata=meta)
        captured_at = utc_now_instant()
        ts = format_utc_instant(captured_at)

        # Stamp the computed identifier only when we got one, so a hashing
        # failure never clobbers a swhid already on the intent.
        swhid = _compute_source_swhid(layout.upstream, log)
        if swhid:
            log("system", "info", f"source swhid: {swhid}")

        if args.mode == "download":
            # Settle the concrete commit onto the intent (like swhid) so the seal
            # can pin a re-fetch; only meaningful for git sources. Read HEAD from
            # the acquired tree — empty when it carries no git history.
            revision = resolved_git_head(layout.upstream) if args.source_type == "git" else ""
            if revision:
                log("system", "info", f"source revision: {revision}")
            transition = record_source_acquisition(
                ree,
                acquired_by="download",
                captured_at=captured_at,
                snapshot_archive=ReePath(SNAPSHOT_FILENAME),
                origin_url=args.origin_url,
                source_type=args.source_type,
                resolved_commit=GitRevision(revision) if revision else None,
                swhid=Swhid(swhid) if swhid else None,
            )
        else:
            transition = record_source_acquisition(
                ree,
                acquired_by="upload",
                captured_at=captured_at,
                snapshot_archive=ReePath(SNAPSHOT_FILENAME),
                uploaded_archive=ReePath(args.archive_name),
                swhid=Swhid(swhid) if swhid else None,
            )

        intent = transition.authored.intent
        state = transition.evidence.state

        updated = meta.model_copy(
            update={
                "ree_intent": intent,
                "ree_state": state,
                "status": "ready",
                "updated_at": ts,
                "external_ref": intent.origin_url or None,
            }
        )
        store.write_metadata(updated)
    except Exception as exc:
        log("system", "error", f"metadata update failed: {exc}")
        return failed_from_exception(exc, f"metadata update failed: {exc}")

    log("system", "info", "update_source_metadata succeeded")
    return ActionResult(status="succeeded", exit_code=0)
