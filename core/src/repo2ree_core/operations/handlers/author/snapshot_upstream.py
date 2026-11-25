from __future__ import annotations

import tarfile

from repo2ree_core.persistence.files import pack_directory_tar_gz
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.frames import LogSink
from repo2ree_ree.digest import Digest
from repo2ree_ree.layout import GIT_DIR

SNAPSHOT_FAILURES = (OSError, tarfile.TarError)


def freeze_upstream(layout: ReeLayout, *, log: LogSink) -> Digest:
    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    return pack_directory_tar_gz(layout.upstream, layout.snapshot_archive, left_out=frozenset({GIT_DIR}))
