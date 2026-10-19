"""Collect behaviour evidence from a running deployment into a recording.

Everything comes through the control plane, the one part of a distributed
deployment a collector can rely on reaching: the owners' journals and persisted
state from ``/api/v1/behaviour``, and each REE as the product downloads it (a copy a
client kept is placed by the control plane's record of serving it). Each source is
written with its origin and, for snapshots of a running system, the journal
positions it was taken between.
"""

from repo2ree_collect.client import ControlPlane, UnreachableError
from repo2ree_collect.collect import (
    archive,
    collect_control_plane,
    download_archive,
    finish,
    kept_archives,
    spans,
    start,
)

__all__ = [
    "ControlPlane",
    "UnreachableError",
    "archive",
    "collect_control_plane",
    "download_archive",
    "finish",
    "kept_archives",
    "spans",
    "start",
]
