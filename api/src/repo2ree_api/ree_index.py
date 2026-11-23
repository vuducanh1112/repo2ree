from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.deposit.models import ArchiveBindingAttestation
from repo2ree_ree.model import Ree, ReeCatalogMetadata


class ReeIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_digest: str
    name: str
    sealed_at: str
    catalog_metadata: ReeCatalogMetadata = Field(default_factory=ReeCatalogMetadata)
    ree_version: str = ""

    archive_attestations: list[ArchiveBindingAttestation] = Field(default_factory=list)

    @property
    def is_deposited(self) -> bool:
        return bool(self.archive_attestations)


def entry_from_ree(ree: Ree) -> ReeIndexEntry:
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


def _entry_sort_key(entry: ReeIndexEntry) -> tuple[str, str]:
    return entry.sealed_at, entry.subject_digest


class ReeIndex:
    def __init__(self, index_file: Path):
        self._path = index_file
        self._lock = RLock()

    def record_seal(self, entry: ReeIndexEntry) -> ReeIndexEntry:
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
