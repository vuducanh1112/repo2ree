from __future__ import annotations

from repo2ree_core.bundle.seal import seal_workspace_ree
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.command import SealReeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_seal_ree(
    args: SealReeArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "seal_ree canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    storage_root = layout.root.parent
    ree_id = layout.root.name

    try:
        outputs = seal_workspace_ree(
            storage_root,
            ree_id,
            source_included=args.source_included,
            runtime_included=args.runtime_included,
            results_included=args.results_included,
            sealed_at=utc_now(),
        )
    except Exception as exc:
        log("system", "error", f"seal_ree failed: {exc}")
        return ActionResult.failed("internal", f"seal_ree failed: {exc}")

    log("system", "info", f"REE sealed: {outputs.seal_hash}")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump())
