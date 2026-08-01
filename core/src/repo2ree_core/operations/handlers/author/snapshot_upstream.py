"""Handler for the snapshot_upstream operation.

Packs /ree/upstream into /ree/snapshot.tar.gz. No-op if upstream is absent.
The archive is hashed while it is written; the digest is persisted on the
state (the chain root of every step's input slice) and recorded in the
run's receipt.
"""

from __future__ import annotations

import tarfile

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.ree.receipt import SnapshotUpstreamReceipt
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import log_step_outcome, settle_step
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import pack_directory_tar_gz
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import persist_snapshot_digest
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_OPERATION = "snapshot_upstream"


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
    layout = ReeLayout.in_workbench()

    if not layout.upstream.is_dir():
        log("system", "warn", "upstream/ does not exist — skipping snapshot")
        return ActionResult(status="succeeded", exit_code=0)

    timer = OperationTimer.start()
    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    # Packing walks and reads an arbitrary source tree: an unreadable file, a
    # broken link, a device node tarfile refuses. All of it is a fact about that
    # tree rather than a defect here, which is what makes it the caller's news.
    try:
        snapshot_digest = pack_directory_tar_gz(layout.upstream, layout.snapshot_archive)
    except (OSError, tarfile.TarError) as exc:
        log("system", "error", f"snapshot failed: {exc}")
        log_step_outcome(_OPERATION, "failed", timer.finish(), log=log)
        return failed_from_exception(exc, f"snapshot failed: {exc}")

    persist_snapshot_digest(ReeDirectory(layout), snapshot_digest, log=log)
    settle_step(
        layout,
        lambda envelope: SnapshotUpstreamReceipt(**envelope, snapshot_digest=snapshot_digest),
        operation=_OPERATION,
        run_id=run_id,
        timer=timer,
        status="succeeded",
        log=log,
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=SnapshotUpstreamOutputs(
            snapshot_archive=layout.snapshot_archive.name,
            snapshot_digest=snapshot_digest,
        ).model_dump(),
    )
