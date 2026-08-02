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

Every field except ``archive_attestations`` is copied verbatim from the sealed
manifest, which means an entry is reconstructible from a downloaded bundle
alone. That is what lets a peer harvest this index without trusting it: fetch
the bundle, rebuild the entry, compare. The attestation list is the only part
learned *after* sealing, and it is checkable independently by resolving the
identifier it names.

Nothing node-local belongs on an entry — not the ``ree_id``, not whether this
node still holds the bundle bytes. The entry is publishable as-is, with no
filtering pass before export, so a local path cannot leak into a snapshot by
omission. Bundle retention is tracked separately.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.deposit.models import ArchiveBindingAttestation
from repo2ree_core.domain.ree.intent import ReeCatalogMetadata

# ================================================
# Data Models
# ================================================


class ReeIndexEntry(BaseModel):
    """One sealed REE, plus whatever archives have since been claimed to hold it."""

    model_config = ConfigDict(extra="forbid")

    # Content identity: ``ReeState.seal_hash``, e.g. "sha256:…". The primary
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


def entry_from_manifest(payload: Mapping[str, Any]) -> ReeIndexEntry:
    """Project a sealed REE's manifest onto its index entry.

    The manifest is the only admissible source. It would be easier to read these
    fields off the workbench document the seal route already holds, but that
    document's ``name`` is the REE name from its record, while the manifest
    substitutes ``ree-<ree_id prefix>`` when the intent carries none — so a
    peer rebuilding this entry from a downloaded bundle would disagree with us
    about the same digest. ``ree_version`` has the same requirement for a
    different reason: it must be the generation the *workbench* sealed with,
    which can lag this service's ``REE_MANIFEST_VERSION`` whenever the executor
    bundle is older than the API.

    Raises ``ValueError`` for an unsealed manifest: without a digest there is no
    identity to file the entry under.
    """
    seal_hash = str(payload.get("seal_hash") or "")
    if not seal_hash:
        raise ValueError("manifest carries no seal_hash; only a sealed REE can be indexed")
    return ReeIndexEntry(
        subject_digest=seal_hash,
        name=str(payload.get("name") or ""),
        sealed_at=str(payload.get("sealed_at") or ""),
        catalog_metadata=ReeCatalogMetadata.model_validate(payload.get("catalog_metadata") or {}),
        ree_version=str(payload.get("ree_version") or ""),
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
    ``os.replace``, so a torn write cannot corrupt the file, and read-modify-write
    is not serialized across processes (last writer wins) — fine for the
    single-process deployments this backs.

    Two properties differ from that registry and will eventually outgrow a JSON
    file: this grows without bound, and it is read-mostly under an ordered cursor
    query. SQLite is the migration when the snapshot endpoint gets slow, not
    before — the entries are the contract, the file is not.
    """

    def __init__(self, index_file: Path):
        self._path = index_file

    def record_seal(self, entry: ReeIndexEntry) -> ReeIndexEntry:
        """Upsert the manifest half of an entry, preserving its attestations.

        Re-sealing unchanged content reproduces the same digest by design, so
        this lands on the existing entry rather than a new one. The attestations
        already recorded there survive: they are claims about the digest, which
        has not changed, and a DOI cannot be withdrawn just because the author
        re-sealed. Returns the stored entry.
        """
        data = self._read()
        existing = data.get(entry.subject_digest)
        if existing is not None:
            entry = entry.model_copy(
                update={"archive_attestations": ReeIndexEntry.model_validate(existing).archive_attestations}
            )
        data[entry.subject_digest] = entry.model_dump()
        self._write(data)
        return entry

    def append_attestation(self, attestation: ArchiveBindingAttestation) -> ReeIndexEntry:
        """Record one archive binding against the REE it names.

        Idempotent on ``(archive, identifier)``: republishing or replaying the
        same deposit must not double the list. A binding for an unknown digest
        raises — locally that means publishing a deposit for an REE this node
        never sealed, which is a bug, not a client error. Harvesting a peer's
        attestations is a different path and must fetch the entry first.
        """
        data = self._read()
        record = data.get(attestation.subject_digest)
        if record is None:
            raise KeyError(f"no index entry for {attestation.subject_digest}")
        entry = ReeIndexEntry.model_validate(record)
        seen = {(existing.archive, existing.identifier) for existing in entry.archive_attestations}
        if (attestation.archive, attestation.identifier) not in seen:
            entry = entry.model_copy(update={"archive_attestations": [*entry.archive_attestations, attestation]})
            data[entry.subject_digest] = entry.model_dump()
            self._write(data)
        return entry

    def get(self, subject_digest: str) -> ReeIndexEntry | None:
        record = self._read().get(subject_digest)
        return None if record is None else ReeIndexEntry.model_validate(record)

    def list_all(self, *, deposited_only: bool = False) -> list[ReeIndexEntry]:
        """Every entry in the index's stable total order, newest last.

        ``deposited_only`` is the filter a published snapshot uses: an entry with
        no attestations is a local seal that no archive has accepted, so it is
        real to this node but not yet citable by anyone else.
        """
        entries = [ReeIndexEntry.model_validate(record) for record in self._read().values()]
        if deposited_only:
            entries = [entry for entry in entries if entry.is_deposited]
        entries.sort(key=_entry_sort_key)
        return entries

    def _read(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        parsed: dict[str, dict[str, object]] = json.loads(self._path.read_text(encoding="utf-8"))
        return parsed

    def _write(self, data: dict[str, dict[str, object]]) -> None:
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
