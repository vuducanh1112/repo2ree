"""Freezing ``upstream/`` into the REE's canonical snapshot archive.

Effect only, and not an operation: freezing is one step of the acquire
lifecycle in :mod:`repo2ree_core.operations.handlers.author.acquire_source`,
which holds the hydrated REE the resulting digest belongs to and commits it
there. Nothing else may record it — a digest persisted from inside this step
is how a receipt used to end up claiming one the state never received.
"""

from __future__ import annotations

import tarfile

from repo2ree_core.digests import Digest
from repo2ree_core.persistence.files import pack_directory_tar_gz
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.log import LogSink

# Packing walks and reads an arbitrary source tree: an unreadable file, a broken
# link, a device node tarfile refuses. All of it is a fact about that tree rather
# than a defect here, which is what makes it the caller's news.
SNAPSHOT_FAILURES = (OSError, tarfile.TarError)


def freeze_upstream(layout: ReeLayout, *, log: LogSink) -> Digest:
    """Pack ``upstream/`` into the snapshot archive and return its digest.

    Raises on any packing failure; the caller decides what that means for the
    acquisition it is part of.
    """
    log("system", "info", f"snapshotting {layout.upstream} → {layout.snapshot_archive}")
    return pack_directory_tar_gz(layout.upstream, layout.snapshot_archive)
