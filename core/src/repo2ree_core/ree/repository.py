"""Hydrate the canonical :class:`domain.ree.Ree` from its persisted parts.

Receipt schemas and persistence are part of the REE's durable record, so this
repository can assemble the domain object without depending on evidence
interpretation or application handlers.
"""

from __future__ import annotations

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.primitives import ReeId, ReePath, parse_utc_instant
from repo2ree_core.domain.ree import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    ReeIdentity,
    ReePublications,
    SealedRee,
)
from repo2ree_core.domain.ree_session import is_sealed
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.receipts import load_author_receipts, load_receipts
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata


def load_ree(
    layout: ReeLayout,
    store: ReeStore | None = None,
    *,
    metadata: WorkspaceMetadata | None = None,
) -> Ree:
    """Read one complete REE domain snapshot.

    ``overlay/`` is the authored file source of truth; ``workspace/`` is a
    materialized execution view and therefore never contributes authored state.
    """

    ree_store = store or ReeStore(layout)
    persisted = metadata or ree_store.read_metadata()
    files = tuple(
        AuthoredFile(
            path=ReePath(relative.as_posix()),
            digest=digest_file(ree_store.overlay.absolute(relative)),
            size=ree_store.overlay.absolute(relative).stat().st_size,
        )
        for relative in ree_store.overlay.iter_files()
    )
    selected_by_step = load_author_receipts(layout)
    session = persisted.ree_session
    sealed = (
        SealedRee(
            seal_hash=session.seal_hash,
            sealed_at=session.sealed_at,
            source_included=session.source_included,
            runtime_included=session.runtime_included,
            results_included=session.results_included,
        )
        if is_sealed(session) and session.seal_hash is not None and session.sealed_at is not None
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
            session_projection=session,
        ),
        publications=ReePublications(sealed=sealed),
    )
