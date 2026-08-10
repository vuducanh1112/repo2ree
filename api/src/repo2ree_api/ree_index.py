"""The durable record of sealed REEs and the archive bindings claimed for them.

A sibling of :mod:`repo2ree_api.control` rather than part of it, because the
collections in there are all liveness projections: connected agents, active REEs
and active runs are derived from current infrastructure — presence in those
lists *is* liveness, and nothing is ever written to them (see
``control/fleet.py``). An index entry is the opposite: it is
written explicitly at seal time and must outlive the workbench that produced
it, because ``deleteRee`` removes the container *and its backing storage*. A
deposited REE whose record died with its workbench is unciteable.

The key is ``subject_digest`` — the content digest computed at seal — and never
``ree_id``, which is a node-local ``uuid4`` handle. Two nodes holding the same
REE must agree on one entry, so the identity has to come from the content.

Every field except ``archive_attestations`` is projected from the sealed
portable aggregate. A peer can therefore fetch a bundle, parse its REE, rebuild
the entry, and compare it. The attestation list is the only part learned after
sealing.

Nothing node-local belongs on an entry — not the ``ree_id``, not whether this
node still holds the bundle bytes. The entry is publishable as-is, with no
filtering pass before export, so a local path cannot leak into a snapshot by
omission. Bundle retention is tracked separately.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.deposit.models import ArchiveBindingAttestation
from repo2ree_core.domain.ree.model import Ree, ReeCatalogMetadata

# ================================================
# Data Models
# ================================================


class ReeIndexEntry(BaseModel):
    """One sealed REE, plus whatever archives have since been claimed to hold it."""

    model_config = ConfigDict(extra="forbid")

    # Content identity: ``Ree.seal.ree_digest``, e.g. "sha256:…". The primary
    # key here and the join key the attestations carry.
    subject_digest: str
    name: str
    sealed_at: str
    catalog_metadata: ReeCatalogMetadata = Field(default_factory=ReeCatalogMetadata)
    # The manifest generation this entry was built from. ``split_manifest_payload``
    # rejects a manifest whose version it does not know, so once
    # REE_MANIFEST_VERSION bumps the index holds two generations at once and a
    # reader needs to tell "I cannot parse this one" from "this one is corrupt".
    ree_version: str = ""

    # ── learned after sealing ──
    # Append-only. Qualified rather than bare ``attestations`` because the same
    # subject will later carry other claim types (verification receipts, digest
    # migrations); see docs/research/sealing.md.
    archive_attestations: list[ArchiveBindingAttestation] = Field(default_factory=list)

    @property
    def is_deposited(self) -> bool:
        """Whether any archive has issued an identifier for this REE.

        Deposit is a predicate over the attestations, not a separate lifecycle:
        an entry exists from the moment the REE is sealed, and depositing only
        appends to it.
        """
        return bool(self.archive_attestations)


def entry_from_ree(ree: Ree) -> ReeIndexEntry:
    """Project a sealed portable aggregate onto its durable index entry."""
    if ree.seal is None:
        raise ValueError("only a sealed REE can be indexed")
    definition = ree.subject.definition
    return ReeIndexEntry(
        subject_digest=ree.seal.ree_digest,
        name=definition.name,
        sealed_at=ree.seal.sealed_at.isoformat().replace("+00:00", "Z"),
        catalog_metadata=definition.catalog,
        ree_version=str(ree.subject.schema_version),
    )


# ================================================
# Store
# ================================================


def _entry_sort_key(entry: ReeIndexEntry) -> tuple[str, str]:
    """The index's stable total order, and the basis of every published cursor.

    ``sealed_at`` alone is not unique, so ``subject_digest`` breaks ties. Both
    components are intrinsic to the sealed content, so the order is identical on
    every node that holds the same entries — which is what makes a snapshot hash
    comparable between peers and a ``since=`` cursor resumable across them.
    Changing this invalidates every snapshot already published.
    """
    return entry.sealed_at, entry.subject_digest


class ReeIndex:
    """JSON-file store of :class:`ReeIndexEntry`, keyed by ``subject_digest``.

    Same durability shape as ``WorkbenchRegistry``: write-to-temp plus
    ``os.replace``, so a torn write cannot corrupt the file. Read-modify-write
    transactions are serialized across threads in this process. The JSON
    backend does not coordinate multiple processes; deployments must use one
    API worker until the store moves to transactional storage.

    Two properties differ from that registry and will eventually outgrow a JSON
    file: this grows without bound, and it is read-mostly under an ordered cursor
    query. SQLite is the migration when the snapshot endpoint gets slow, not
    before — the entries are the contract, the file is not.
    """

    def __init__(self, index_file: Path):
        self._path = index_file
        self._lock = RLock()

    def record_seal(self, entry: ReeIndexEntry) -> ReeIndexEntry:
        """Upsert the manifest half of an entry, preserving its attestations.

        Re-sealing unchanged content reproduces the same digest by design, so
        this lands on the existing entry rather than a new one. The attestations
        already recorded there survive: they are claims about the digest, which
        has not changed, and a DOI cannot be withdrawn just because the author
        re-sealed. Returns the stored entry.
        """
        with self._lock:
            data = self._read_unlocked()
            existing = data.get(entry.subject_digest)
            if existing is not None:
                entry = entry.model_copy(
                    update={"archive_attestations": ReeIndexEntry.model_validate(existing).archive_attestations}
                )
            data[entry.subject_digest] = entry.model_dump()
            self._write_unlocked(data)
            return entry

    def append_attestation(self, attestation: ArchiveBindingAttestation) -> ReeIndexEntry:
        """Record one archive binding against the REE it names.

        Idempotent on ``(archive, identifier)``: republishing or replaying the
        same deposit must not double the list. A binding for an unknown digest
        raises — locally that means publishing a deposit for an REE this node
        never sealed, which is a bug, not a client error. Harvesting a peer's
        attestations is a different path and must fetch the entry first.
        """
        with self._lock:
            data = self._read_unlocked()
            record = data.get(attestation.subject_digest)
            if record is None:
                raise KeyError(f"no index entry for {attestation.subject_digest}")
            entry = ReeIndexEntry.model_validate(record)
            seen = {(existing.archive, existing.identifier) for existing in entry.archive_attestations}
            if (attestation.archive, attestation.identifier) not in seen:
                entry = entry.model_copy(update={"archive_attestations": [*entry.archive_attestations, attestation]})
                data[entry.subject_digest] = entry.model_dump()
                self._write_unlocked(data)
            return entry

    def get(self, subject_digest: str) -> ReeIndexEntry | None:
        with self._lock:
            record = self._read_unlocked().get(subject_digest)
        return None if record is None else ReeIndexEntry.model_validate(record)

    def list_all(self, *, deposited_only: bool = False) -> list[ReeIndexEntry]:
        """Every entry in the index's stable total order, newest last.

        ``deposited_only`` is the filter a published snapshot uses: an entry with
        no attestations is a local seal that no archive has accepted, so it is
        real to this node but not yet citable by anyone else.
        """
        with self._lock:
            records = list(self._read_unlocked().values())
        entries = [ReeIndexEntry.model_validate(record) for record in records]
        if deposited_only:
            entries = [entry for entry in entries if entry.is_deposited]
        entries.sort(key=_entry_sort_key)
        return entries

    def _read_unlocked(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        parsed: dict[str, dict[str, object]] = json.loads(self._path.read_text(encoding="utf-8"))
        return parsed

    def _write_unlocked(self, data: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, sort_keys=True)
        fd, tmp = tempfile.mkstemp(prefix=self._path.name + ".", suffix=".tmp", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            Path(tmp).replace(self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
