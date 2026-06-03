"""Handler for the snapshot_upstream operation.

Packs /ree/upstream into /ree/snapshot.tar.gz. No-op if upstream is absent.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_core.storage.extract import pack_directory_tar_gz
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.working_environment.base import CancelCheck


def handle_snapshot_upstream(
    *,
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

    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    try:
        pack_directory_tar_gz(layout.upstream, layout.snapshot_archive)
    except Exception as exc:
        log("system", "error", f"snapshot failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "snapshot_upstream succeeded")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"snapshot_archive": layout.snapshot_archive.name},
    )
