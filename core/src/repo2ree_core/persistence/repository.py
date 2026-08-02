"""Read and write the canonical :class:`domain.ree.Ree` as one value.

Receipt schemas and persistence are part of the REE's durable record, so this
repository can assemble the domain object without depending on evidence
interpretation or application handlers.

:func:`load_ree` and :func:`save_ree` are a pair, and the pairing is what makes
the domain model the REE's head rather than a read-only projection of it: a
caller hydrates a whole ``Ree``, transforms it with the pure functions in
``domain.ree.transitions``, and hands the whole thing back. Nothing else may
write the head. That is why the per-part writers on :class:`ReeDirectory`
(``write_intent``, ``write_state``) each re-read the record and merge — they
predate this and silently reconcile, which is precisely what the
compare-and-write below refuses to do.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.primitives import ReeId, ReePath, ReeRevision, parse_utc_instant
from repo2ree_core.domain.ree.model import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    ReeIdentity,
    Seal,
)
from repo2ree_core.domain.ree.state import is_sealed
from repo2ree_core.domain.ree.transitions import SourceSlot, revision_of
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import load_author_receipts, load_receipts, record_receipt
from repo2ree_core.persistence.record import ReeRecord, ReeStatus
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink


class ReeRevisionConflictError(RuntimeError):
    """The head moved between the hydrate this save was planned from and the save.

    Raised rather than merged: a save carries a whole head, so reconciling it
    against a newer one would mean picking which writer's fields survive — a
    decision no store is in a position to make.
    """


def layout_for(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def directory_for(storage_root: Path, ree_id: str) -> ReeDirectory:
    return ReeDirectory(layout_for(storage_root, ree_id))


def load_ree(
    layout: ReeLayout,
    store: ReeDirectory | None = None,
    *,
    record: ReeRecord | None = None,
) -> Ree:
    """Read one complete REE domain snapshot.

    ``overlay/`` is the authored file source of truth; ``workspace/`` is a
    materialized execution view and therefore never contributes authored state.
    """

    ree_store = store or ReeDirectory(layout)
    persisted = record or ree_store.read_record()
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
    seal = (
        Seal(
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
        seal=seal,
    )


def observe_source_slot(layout: ReeLayout, *, upload_token: str = "") -> SourceSlot:
    """What the disk says about the source slot, in one reading.

    The counterpart of the ``source_available`` flag on the state, and worth
    reading separately: an acquisition that performed its effect and died
    before committing leaves the two disagreeing, and that disagreement is the
    only evidence such a run ever existed.

    ``upload_token`` narrows the staging check to the one archive an upload
    acquisition is about, so a *different* upload still in flight neither
    satisfies this one's precondition nor blocks it.
    """
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
    expected_revision: ReeRevision,
    status: ReeStatus | None = None,
    log: LogSink,
) -> None:
    """Commit one whole REE head, refusing if it moved since it was hydrated.

    Evidence goes to ``runs/`` first and the record last, and that order is the
    crash contract: receipt files are append-only and keyed by run id, so a
    process that dies between the two leaves history nothing else will read as
    current. The reverse order would leave a state claiming evidence that is not
    on disk — the failure the reader has no way to detect.

    Callers hold the per-REE dispatch serialization, so the read-check-write
    below is atomic against every other command on this REE. The check earns its
    keep anyway: it catches a writer that bypassed this function.
    """
    persisted = load_ree(layout, store)
    current = revision_of(persisted)
    if current != expected_revision:
        raise ReeRevisionConflictError(
            f"REE {ree.identity.ree_id} changed while the operation ran (expected {expected_revision}, found {current})"
        )

    already_recorded = {receipt.run_id for receipt in persisted.evidence.history}
    for receipt in ree.evidence.history:
        if receipt.run_id not in already_recorded:
            record_receipt(layout, receipt, log=log)
    store.write_record(
        store.read_record().with_head(
            ree.authored.intent,
            ree.evidence.state,
            at=utc_now(),
            status=status,
        )
    )
