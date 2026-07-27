"""Handler for the snapshot_upstream operation.

Packs /ree/upstream into /ree/snapshot.tar.gz. No-op if upstream is absent.
The archive is hashed while it is written; the digest is persisted on the
session (the chain root of every step's input slice) and recorded in the
run's receipt.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.evidence.receipts.models import SnapshotUpstreamReceipt, receipt_envelope
from repo2ree_core.evidence.receipts.store import persist_snapshot_digest, record_receipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.ree.files import pack_directory_tar_gz
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class SnapshotUpstreamOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_archive: str
    snapshot_digest: str | None


def handle_snapshot_upstream(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "snapshot_upstream canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()

    if not layout.upstream.is_dir():
        log("system", "warn", "upstream/ does not exist — skipping snapshot")
        return ActionResult(status="succeeded", exit_code=0)

    timer = OperationTimer.start()
    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    try:
        snapshot_digest = pack_directory_tar_gz(layout.upstream, layout.snapshot_archive)
    except Exception as exc:
        timing = timer.finish()
        log(
            "system",
            "error",
            f"snapshot failed after {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms}): {exc}",
        )
        return ActionResult.failed("internal", f"snapshot failed: {exc}")

    persist_snapshot_digest(ReeStore(layout), snapshot_digest, log=log)
    timing = timer.finish()
    record_receipt(
        layout,
        SnapshotUpstreamReceipt(
            **receipt_envelope(run_id, timing, "succeeded"),
            snapshot_digest=snapshot_digest,
        ),
        log=log,
    )

    log(
        "system",
        "info",
        f"snapshot_upstream succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=SnapshotUpstreamOutputs(
            snapshot_archive=layout.snapshot_archive.name,
            snapshot_digest=snapshot_digest,
        ).model_dump(),
    )
