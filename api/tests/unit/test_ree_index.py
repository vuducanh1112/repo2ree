"""The durable half of the control plane: what survives a workbench going away.

The store is exercised against a throwaway file rather than the module-level
singleton, so these assertions say something about ``ReeIndex`` itself and not
about whichever state a previous test left behind.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from repo2ree_api.deposit.models import ArchiveBindingAttestation
from repo2ree_api.ree_index import ReeIndex, ReeIndexEntry, entry_from_ree
from repo2ree_core.domain.ree.model import Ree, ReeCatalogMetadata, ReeDefinition, ReeSeal, ReeSubject

# ================================================
# Helpers
# ================================================


def sealed_ree(seal_hash: str, *, name: str = "demo", sealed_at: str = "2026-07-29T00:00:00Z") -> Ree:
    subject = ReeSubject(
        definition=ReeDefinition(
            name=name,
            catalog=ReeCatalogMetadata(description="a demo", keywords=("repro",)),
        )
    )
    seal = ReeSeal.model_validate({"sealed_at": sealed_at, "ree_digest": seal_hash})
    # These store tests use readable digest labels to exercise ordering. The
    # aggregate digest invariant itself is covered in core domain tests.
    return Ree.model_construct(subject=subject, seal=seal)


def binding(
    subject_digest: str,
    *,
    archive: str = "zenodo",
    identifier: str = "doi:10.5281/zenodo.1",
) -> ArchiveBindingAttestation:
    return ArchiveBindingAttestation.model_validate(
        {"subject_digest": subject_digest, "archive": archive, "identifier": identifier}
    )


@pytest.fixture
def index(tmp_path: Path) -> ReeIndex:
    return ReeIndex(tmp_path / "ree-index.json")


# ================================================
# Projection from the manifest
# ================================================


def test_entry_is_projected_from_the_ree() -> None:
    entry = entry_from_ree(sealed_ree("sha256:aaa"))

    assert entry.subject_digest == "sha256:aaa"
    assert entry.name == "demo"
    assert entry.sealed_at == "2026-07-29T00:00:00Z"
    assert entry.ree_version == "1"
    assert entry.catalog_metadata.description == "a demo"
    # Nothing is known about archives at seal time.
    assert entry.archive_attestations == []
    assert entry.is_deposited is False


def test_unsealed_ree_cannot_be_indexed() -> None:
    """No digest means no identity to file the entry under."""
    with pytest.raises(ValueError, match="sealed REE"):
        entry_from_ree(Ree())


# ================================================
# Store
# ================================================


def test_entries_round_trip_through_the_file(index: ReeIndex, tmp_path: Path) -> None:
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))

    # A second instance over the same path, i.e. what a restarted service sees.
    reopened = ReeIndex(tmp_path / "ree-index.json")
    stored = reopened.get("sha256:aaa")

    assert stored is not None
    assert stored.name == "demo"


def test_missing_digest_reads_as_absent(index: ReeIndex) -> None:
    assert index.get("sha256:nothing") is None


def test_resealing_preserves_recorded_attestations(index: ReeIndex) -> None:
    """A DOI does not stop being valid because the author sealed again.

    Unchanged content reproduces the same digest by design, so the second seal
    lands on the existing entry. The attestations are claims about that digest,
    which has not changed.
    """
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))
    index.append_attestation(binding("sha256:aaa"))

    stored = index.record_seal(entry_from_ree(sealed_ree("sha256:aaa", name="renamed")))

    assert stored.name == "renamed"
    assert [att.identifier for att in stored.archive_attestations] == ["doi:10.5281/zenodo.1"]


def test_appending_the_same_binding_twice_is_idempotent(index: ReeIndex) -> None:
    """Replaying a publish must not double the list."""
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))
    index.append_attestation(binding("sha256:aaa"))
    stored = index.append_attestation(binding("sha256:aaa"))

    assert len(stored.archive_attestations) == 1


def test_the_same_ree_can_be_deposited_to_several_archives(index: ReeIndex) -> None:
    """The reason a deposit is a list and not a ``doi`` field."""
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))
    index.append_attestation(binding("sha256:aaa"))
    stored = index.append_attestation(binding("sha256:aaa", archive="dataverse", identifier="hdl:1902.1/1"))

    assert {att.archive for att in stored.archive_attestations} == {"zenodo", "dataverse"}
    assert stored.is_deposited is True


def test_binding_an_unknown_digest_raises(index: ReeIndex) -> None:
    """Locally this means publishing a deposit for an REE never sealed here."""
    with pytest.raises(KeyError, match="sha256:ghost"):
        index.append_attestation(binding("sha256:ghost"))


# ================================================
# Ordering and filtering
# ================================================


def test_entries_are_ordered_by_seal_time_then_digest(index: ReeIndex) -> None:
    """The published cursor's total order; changing it invalidates snapshots.

    ``sealed_at`` alone is not unique, so equal timestamps fall back to the
    digest — and the order must not depend on insertion, which differs between
    two nodes holding the same entries.
    """
    index.record_seal(entry_from_ree(sealed_ree("sha256:ccc", sealed_at="2026-07-29T02:00:00Z")))
    index.record_seal(entry_from_ree(sealed_ree("sha256:bbb", sealed_at="2026-07-29T01:00:00Z")))
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa", sealed_at="2026-07-29T01:00:00Z")))

    assert [entry.subject_digest for entry in index.list_all()] == ["sha256:aaa", "sha256:bbb", "sha256:ccc"]


def test_deposited_only_hides_seals_no_archive_has_accepted(index: ReeIndex) -> None:
    """What a published snapshot may contain: entries someone else can cite."""
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))
    index.record_seal(entry_from_ree(sealed_ree("sha256:bbb")))
    index.append_attestation(binding("sha256:bbb"))

    assert [entry.subject_digest for entry in index.list_all()] == ["sha256:aaa", "sha256:bbb"]
    assert [entry.subject_digest for entry in index.list_all(deposited_only=True)] == ["sha256:bbb"]


def test_an_entry_carries_nothing_node_local() -> None:
    """Entries are published as-is, with no filtering pass before export.

    A local handle on an entry — the ``ree_id``, a bundle path — could leak into
    a peer snapshot by omission, so the model must not be able to hold one.
    """
    assert "ree_id" not in ReeIndexEntry.model_fields
    with pytest.raises(ValueError, match="ree_id"):
        ReeIndexEntry.model_validate({"subject_digest": "sha256:aaa", "name": "", "sealed_at": "", "ree_id": "abc"})


# ================================================
# Concurrent writes
# ================================================


def _slow_reads(monkeypatch: pytest.MonkeyPatch, index: ReeIndex) -> None:
    """Widen the read-before-write race without reaching inside the lock."""
    real_read = index._read_unlocked

    def slow_read() -> dict[str, dict[str, object]]:
        data = real_read()
        time.sleep(0.05)
        return data

    monkeypatch.setattr(index, "_read_unlocked", slow_read)


def test_concurrent_seals_do_not_lose_entries(index: ReeIndex, monkeypatch: pytest.MonkeyPatch) -> None:
    _slow_reads(monkeypatch, index)
    entries = [
        entry_from_ree(sealed_ree("sha256:aaa")),
        entry_from_ree(sealed_ree("sha256:bbb")),
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(index.record_seal, entry) for entry in entries]
        for future in futures:
            future.result(timeout=2)

    assert {entry.subject_digest for entry in index.list_all()} == {"sha256:aaa", "sha256:bbb"}


def test_concurrent_attestations_are_both_preserved(index: ReeIndex, monkeypatch: pytest.MonkeyPatch) -> None:
    index.record_seal(entry_from_ree(sealed_ree("sha256:aaa")))
    _slow_reads(monkeypatch, index)
    attestations = [
        binding("sha256:aaa", archive="zenodo", identifier="doi:one"),
        binding("sha256:aaa", archive="dataverse", identifier="hdl:two"),
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(index.append_attestation, attestation) for attestation in attestations]
        for future in futures:
            future.result(timeout=2)

    stored = index.get("sha256:aaa")
    assert stored is not None
    assert {(item.archive, item.identifier) for item in stored.archive_attestations} == {
        ("zenodo", "doi:one"),
        ("dataverse", "hdl:two"),
    }
