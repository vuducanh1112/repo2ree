"""Handler for the update_source_metadata operation.

Updates /ree/.workspace.json after a successful source acquisition:
sets status=ready, records snapshot location and source-mode-specific fields.
"""

from __future__ import annotations

from datetime import datetime, timezone

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree import REE
from repo2ree_core.envelope.command import UpdateSourceMetadataArgs
from repo2ree_core.envelope.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout, SNAPSHOT_FILENAME
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck


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
        metadata = store.read_metadata_json()
        ts = _utc_now()

        if args.mode == "upload":
            source = _upload_source(args, ts)
            ree = REE.from_metadata(metadata)
        else:
            source = _download_source(args, ts)
            ree = REE.from_metadata(metadata).model_copy(
                update={"origin_url": args.origin_url, "source_type": args.source_type}
            )

        metadata["source"] = source
        metadata["status"] = "ready"
        metadata["updatedAt"] = ts
        metadata["reeDraft"] = ree.with_source(source).model_dump(exclude_none=True)

        store.write_metadata_json(metadata)
    except Exception as exc:
        log("system", "error", f"metadata update failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "update_source_metadata succeeded")
    return ActionResult(status="succeeded", exit_code=0)


def _download_source(args: UpdateSourceMetadataArgs, ts: str) -> dict:  # type: ignore[type-arg]
    source: dict = {  # type: ignore[type-arg]
        "mode": "download",
        "completedAt": ts,
        "snapshotArchive": SNAPSHOT_FILENAME,
        "snapshotCapturedAt": ts,
        "originUrl": args.origin_url,
        "sourceType": args.source_type,
    }
    if args.resolved_commit:
        source["resolvedCommit"] = args.resolved_commit
    return source


def _upload_source(args: UpdateSourceMetadataArgs, ts: str) -> dict:  # type: ignore[type-arg]
    return {
        "mode": "upload",
        "archiveName": args.archive_name,
        "uploadToken": args.upload_token,
        "completedAt": ts,
        "snapshotArchive": SNAPSHOT_FILENAME,
        "snapshotCapturedAt": ts,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
