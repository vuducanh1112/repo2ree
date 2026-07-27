"""Atomic source preparation workflow.

The control plane supplies intent; the execution plane owns the ordered state
transition. Keeping all steps in one command prevents concurrent source runs
from interleaving between reset, acquire, snapshot, materialize, and metadata.
"""

from __future__ import annotations

from repo2ree_core.envelope.handlers.acquire_source import handle_acquire_source
from repo2ree_core.envelope.handlers.extract_upload import handle_extract_upload
from repo2ree_core.envelope.handlers.materialize_workspace import handle_materialize_workspace
from repo2ree_core.envelope.handlers.snapshot_upstream import handle_snapshot_upstream
from repo2ree_core.envelope.handlers.source_reset import handle_reset_for_source_change
from repo2ree_core.envelope.handlers.update_source_metadata import handle_update_source_metadata
from repo2ree_core.run_script import CancelCheck
from repo2ree_protocol.command import (
    AcquireSourceArgs,
    ExtractUploadArgs,
    PrepareSourceArgs,
    UpdateSourceMetadataArgs,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_prepare_source(
    args: PrepareSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def require_success(operation: str, result: ActionResult) -> ActionResult | None:
        if result.status == "succeeded":
            return None
        log("system", "error", f"prepare_source step {operation} {result.status}")
        return result

    result = handle_reset_for_source_change(log=log, is_canceled=is_canceled)
    if failed := require_success("reset_for_source_change", result):
        return failed

    if args.mode == "download":
        result = handle_acquire_source(
            AcquireSourceArgs(
                origin_url=args.origin_url,
                source_type=args.source_type,
                revision=args.revision,
            ),
            run_id=run_id,
            log=log,
            is_canceled=is_canceled,
        )
        if failed := require_success("acquire_source", result):
            return failed
        result = handle_snapshot_upstream(run_id=run_id, log=log, is_canceled=is_canceled)
        if failed := require_success("snapshot_upstream", result):
            return failed
        metadata = UpdateSourceMetadataArgs(origin_url=args.origin_url, source_type=args.source_type or "")
    else:
        result = handle_extract_upload(
            ExtractUploadArgs(upload_token=args.upload_token, archive_name=args.archive_name),
            log=log,
            is_canceled=is_canceled,
        )
        if failed := require_success("extract_upload", result):
            return failed
        result = handle_acquire_source(AcquireSourceArgs(), run_id=run_id, log=log, is_canceled=is_canceled)
        if failed := require_success("acquire_source", result):
            return failed
        metadata = UpdateSourceMetadataArgs(
            mode="upload",
            archive_name=args.archive_name,
            upload_token=args.upload_token,
        )
    result = handle_materialize_workspace(log=log, is_canceled=is_canceled)
    if failed := require_success("materialize_workspace", result):
        return failed
    result = handle_update_source_metadata(metadata, log=log, is_canceled=is_canceled)
    if failed := require_success("update_source_metadata", result):
        return failed

    if args.mode == "download":
        outputs = {
            "mode": args.mode,
            "origin_url": args.origin_url,
            "source_type": args.source_type,
            "revision": args.revision,
        }
    else:
        outputs = {
            "mode": args.mode,
            "upload_token": args.upload_token,
            "archive_name": args.archive_name,
        }
    return ActionResult(status="succeeded", outputs=outputs)
