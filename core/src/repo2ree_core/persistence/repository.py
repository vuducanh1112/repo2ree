"""Persistence boundary for the portable :class:`Ree` aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.domain.primitives import Digest
from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.transitions import revision_of, validate_seal
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout


class ReeRevisionConflictError(RuntimeError):
    """The REE subject moved after an operation was planned."""


@dataclass(frozen=True)
class SourceSlot:
    upstream_populated: bool
    snapshot_archive_present: bool
    staged_upload_present: bool


def layout_for(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def directory_for(storage_root: Path, ree_id: str) -> ReeDirectory:
    return ReeDirectory(layout_for(storage_root, ree_id))


def load_ree(layout: ReeLayout, store: ReeDirectory | None = None) -> Ree:
    ree_store = store or ReeDirectory(layout)
    ree = ree_store.read_ree()
    validate_seal(ree)
    return ree


def observe_source_slot(layout: ReeLayout, *, upload_token: str = "") -> SourceSlot:
    return SourceSlot(
        upstream_populated=layout.upstream.is_dir() and any(layout.upstream.iterdir()),
        snapshot_archive_present=layout.snapshot_archive.exists(),
        staged_upload_present=bool(upload_token) and layout.upload_staging_file(upload_token).is_file(),
    )


def save_ree(
    layout: ReeLayout,
    store: ReeDirectory,
    ree: Ree,
    *,
    expected_revision: Digest,
) -> None:
    """Compare and atomically replace the serialized aggregate."""
    persisted = load_ree(layout, store)
    current = revision_of(persisted)
    if current != expected_revision:
        raise ReeRevisionConflictError(
            f"REE changed while the operation ran (expected {expected_revision}, found {current})"
        )
    validate_seal(ree)
    store.write_ree(ree)
