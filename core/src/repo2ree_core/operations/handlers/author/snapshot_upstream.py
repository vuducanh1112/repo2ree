"""Handler for the snapshot_upstream operation.

Packs /ree/upstream into /ree/snapshot.tar.gz, hashing the archive as it is
written.

Effect only: the digest is *returned*, never persisted here. Freezing the
upstream tree is one effect of the acquire lifecycle, and only that lifecycle
is in a position to record what the freeze produced — it holds the hydrated
REE the digest belongs to. Persisting it from inside this step is what used to
let a receipt claim a digest the state never received.
"""

from __future__ import annotations

import tarfile

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import Digest
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.files import pack_directory_tar_gz
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

# Packing walks and reads an arbitrary source tree: an unreadable file, a broken
# link, a device node tarfile refuses. All of it is a fact about that tree rather
# than a defect here, which is what makes it the caller's news.
SNAPSHOT_FAILURES = (OSError, tarfile.TarError)


class SnapshotUpstreamOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_archive: str
    snapshot_digest: str | None


def freeze_upstream(layout: ReeLayout, *, log: LogSink) -> Digest:
    """Pack ``upstream/`` into the snapshot archive and return its digest.

    Raises on any packing failure; the caller decides what that means for the
    acquisition it is part of.
    """
    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    return pack_directory_tar_gz(layout.upstream, layout.snapshot_archive)


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

    try:
        snapshot_digest = freeze_upstream(layout, log=log)
    except SNAPSHOT_FAILURES as exc:
        log("system", "error", f"snapshot failed: {exc}")
        return failed_from_exception(exc, f"snapshot failed: {exc}")

    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=SnapshotUpstreamOutputs(
            snapshot_archive=layout.snapshot_archive.name,
            snapshot_digest=snapshot_digest,
        ).model_dump(),
    )
