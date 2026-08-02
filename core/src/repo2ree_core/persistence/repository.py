"""Hydrate the canonical :class:`domain.ree.Ree` from its persisted parts.

Receipt schemas and persistence are part of the REE's durable record, so this
repository can assemble the domain object without depending on evidence
interpretation or application handlers.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.primitives import ReeId, ReePath, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    ReeIdentity,
    ReePublications,
    SealedRee,
)
from repo2ree_core.domain.ree.state import is_sealed
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import load_author_receipts, load_receipts
from repo2ree_core.persistence.sidecar import ReeSidecar


def layout_for(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def directory_for(storage_root: Path, ree_id: str) -> ReeDirectory:
    return ReeDirectory(layout_for(storage_root, ree_id))


def load_ree(
    layout: ReeLayout,
    store: ReeDirectory | None = None,
    *,
    sidecar: ReeSidecar | None = None,
) -> Ree:
    """Read one complete REE domain snapshot.

    ``overlay/`` is the authored file source of truth; ``workspace/`` is a
    materialized execution view and therefore never contributes authored state.
    """

    ree_store = store or ReeDirectory(layout)
    persisted = sidecar or ree_store.read_sidecar()
    files = tuple(
        AuthoredFile(
            path=ReePath(relative.as_posix()),
            digest=digest_file(ree_store.overlay.absolute(relative)),
            size=ree_store.overlay.absolute(relative).stat().st_size,
        )
        for relative in ree_store.overlay.iter_files()
    )
    selected_by_step = load_author_receipts(layout)
    state = persisted.ree_state
    sealed = (
        SealedRee(
            seal_hash=state.seal_hash,
            sealed_at=state.sealed_at,
            source_included=state.source_included,
            runtime_included=state.runtime_included,
            results_included=state.results_included,
        )
        if is_sealed(state) and state.seal_hash is not None and state.sealed_at is not None
        else None
    )
    return Ree(
        identity=ReeIdentity(
            ree_id=ReeId(persisted.ree_id),
            created_at=parse_utc_instant(persisted.created_at),
            updated_at=parse_utc_instant(persisted.updated_at),
        ),
        authored=ReeDefinition(intent=persisted.ree_intent, files=files),
        evidence=ReeEvidence(
            history=tuple(load_receipts(layout)),
            selected=tuple(selected_by_step[key] for key in sorted(selected_by_step)),
            state=state,
        ),
        publications=ReePublications(sealed=sealed),
    )
