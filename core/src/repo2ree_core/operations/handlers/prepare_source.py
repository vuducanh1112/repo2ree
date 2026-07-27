"""Atomic source preparation workflow.

The control plane supplies intent; the execution plane owns the ordered state
transition. Keeping all steps in one command prevents concurrent source runs
from interleaving between reset, acquire, snapshot, materialize, and metadata.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers.acquire_source import handle_acquire_source
from repo2ree_core.operations.handlers.extract_upload import handle_extract_upload
from repo2ree_core.operations.handlers.materialize_workspace import handle_materialize_workspace
from repo2ree_core.operations.handlers.snapshot_upstream import handle_snapshot_upstream
from repo2ree_core.operations.handlers.source_reset import handle_reset_for_source_change
from repo2ree_core.operations.handlers.update_source_metadata import handle_update_source_metadata
from repo2ree_protocol.command import (
    AcquireSourceArgs,
    ExtractUploadArgs,
    PrepareSourceArgs,
    UpdateSourceMetadataArgs,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class PrepareSourceOutputs(BaseModel):
    """What the workflow prepared, in the vocabulary of the mode it ran in.

    The fields of the other mode stay unset and are dropped on the way out, so
    a client reads back exactly the inputs that were acted on.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"]
    origin_url: str | None = None
    source_type: str | None = None
    revision: str | None = None
    upload_token: str | None = None
    archive_name: str | None = None


def handle_prepare_source(
    args: PrepareSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def step(operation: str, run: Callable[[], ActionResult]) -> ActionResult | None:
        """Run one sub-step, or the result to stop the whole workflow with.

        Returns ``None`` to carry on. The cancel check is here because these
        sub-handlers are called directly rather than dispatched, so the
        dispatcher's pre-start guard never runs for them — and between two
        steps is exactly where a cancel can be honoured without leaving the
        source half-prepared, since each step is itself atomic.
        """
        if is_canceled():
            log("system", "warn", f"prepare_source canceled before {operation}")
            return ActionResult(status="canceled")
        result = run()
        if result.status == "succeeded":
            return None
        log("system", "error", f"prepare_source step {operation} {result.status}")
        return result

    if halted := step(
        "reset_for_source_change",
        lambda: handle_reset_for_source_change(log=log, is_canceled=is_canceled),
    ):
        return halted

    if args.mode == "download":
        if halted := step(
            "acquire_source",
            lambda: handle_acquire_source(
                AcquireSourceArgs(
                    origin_url=args.origin_url,
                    source_type=args.source_type,
                    revision=args.revision,
                ),
                run_id=run_id,
                log=log,
                is_canceled=is_canceled,
            ),
        ):
            return halted
        if halted := step(
            "snapshot_upstream",
            lambda: handle_snapshot_upstream(run_id=run_id, log=log, is_canceled=is_canceled),
        ):
            return halted
        metadata = UpdateSourceMetadataArgs(origin_url=args.origin_url, source_type=args.source_type or "")
        outputs = PrepareSourceOutputs(
            mode=args.mode,
            origin_url=args.origin_url,
            source_type=args.source_type or "",
            revision=args.revision,
        )
    else:
        if halted := step(
            "extract_upload",
            lambda: handle_extract_upload(
                ExtractUploadArgs(upload_token=args.upload_token, archive_name=args.archive_name),
                log=log,
                is_canceled=is_canceled,
            ),
        ):
            return halted
        if halted := step(
            "acquire_source",
            lambda: handle_acquire_source(AcquireSourceArgs(), run_id=run_id, log=log, is_canceled=is_canceled),
        ):
            return halted
        metadata = UpdateSourceMetadataArgs(
            mode="upload",
            archive_name=args.archive_name,
            upload_token=args.upload_token,
        )
        outputs = PrepareSourceOutputs(
            mode=args.mode,
            upload_token=args.upload_token,
            archive_name=args.archive_name,
        )

    if halted := step(
        "materialize_workspace",
        lambda: handle_materialize_workspace(log=log, is_canceled=is_canceled),
    ):
        return halted
    if halted := step(
        "update_source_metadata",
        lambda: handle_update_source_metadata(metadata, log=log, is_canceled=is_canceled),
    ):
        return halted

    return ActionResult(status="succeeded", outputs=outputs.model_dump(exclude_none=True))
