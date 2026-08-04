from __future__ import annotations

from repo2ree_core.bundle.seal import seal_ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.time_utils import utc_now_instant
from repo2ree_protocol.command import SealReeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_seal_ree(
    args: SealReeArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    storage_root = layout.root.parent
    ree_id = layout.root.name

    try:
        outputs = seal_ree(
            storage_root,
            ree_id,
            source_included=args.source_included,
            runtime_included=args.runtime_included,
            results_included=args.results_included,
            sealed_at=utc_now_instant(),
        )
    except ReePreconditionError as exc:
        # The REE is not in a state that may be sealed — the author's own tree
        # said so, and no retry changes that until they act on it.
        log("system", "error", f"seal_ree refused: {exc}")
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        log("system", "error", f"seal_ree failed: {exc}")
        return failed_from_exception(exc, f"seal_ree failed: {exc}")

    log("system", "info", f"REE sealed: {outputs.ree_digest}")
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))
