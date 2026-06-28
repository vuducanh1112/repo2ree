from __future__ import annotations

from repo2ree_core.container.run_script import CancelCheck, LogSink
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.workspace_ops import seal_workspace_ree
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.command import SealReeArgs
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
            sealed_at=utc_now(),
        )
    except Exception as exc:
        log("system", "error", f"seal_ree failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"REE sealed: {outputs['sealHash']}")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)
