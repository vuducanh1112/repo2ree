"""The REE index endpoint (GET /api/v1/ree-index).

Writes through the real module-level store the app is wired to, since the point
of the route is that it serves what sealing left on disk. Each test clears it
first: the store outlives a request by design, so it also outlives a test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deposit.models import ArchiveBindingAttestation
from repo2ree_api.deps import ree_index
from repo2ree_api.ree_index import entry_from_manifest
from repo2ree_api.settings import service_settings


@pytest.fixture(autouse=True)
def empty_index() -> Iterator[None]:
    """Start and end each test with no index file.

    Removing the file rather than rewriting it also covers the cold-start path:
    a service that has never sealed anything has no file at all, and the route
    must answer an empty page rather than 500.
    """
    service_settings.REE_INDEX_FILE.unlink(missing_ok=True)
    yield
    service_settings.REE_INDEX_FILE.unlink(missing_ok=True)


def seal(digest: str, *, name: str = "demo", sealed_at: str = "2026-07-29T00:00:00Z") -> None:
    ree_index.record_seal(
        entry_from_manifest(
            {
                "seal_hash": digest,
                "name": name,
                "sealed_at": sealed_at,
                "ree_version": "1",
                "catalog_metadata": {"description": "a demo"},
            }
        )
    )


def deposit(digest: str, *, archive: str = "zenodo", identifier: str = "doi:10.5281/zenodo.1") -> None:
    ree_index.append_attestation(
        ArchiveBindingAttestation.model_validate(
            {"subject_digest": digest, "archive": archive, "identifier": identifier}
        )
    )


def test_empty_index_lists_nothing(client: TestClient) -> None:
    resp = client.get("/api/v1/ree-index")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items": [], "next_cursor": None}


def test_a_sealed_ree_is_listed_with_its_manifest_fields(client: TestClient) -> None:
    seal("sha256:aaa", name="demo")

    body = client.get("/api/v1/ree-index").json()

    assert len(body["items"]) == 1
    entry = body["items"][0]
    assert entry["subject_digest"] == "sha256:aaa"
    assert entry["name"] == "demo"
    assert entry["ree_version"] == "1"
    assert entry["catalog_metadata"]["description"] == "a demo"
    # Nothing node-local reaches the wire; an entry is publishable as-is.
    assert "ree_id" not in entry


def test_entries_are_listed_newest_first(client: TestClient) -> None:
    """The reverse of the store's canonical order, which ascends for cursors."""
    seal("sha256:aaa", sealed_at="2026-07-27T00:00:00Z")
    seal("sha256:bbb", sealed_at="2026-07-29T00:00:00Z")
    seal("sha256:ccc", sealed_at="2026-07-28T00:00:00Z")

    body = client.get("/api/v1/ree-index").json()

    assert [item["subject_digest"] for item in body["items"]] == [
        "sha256:bbb",
        "sha256:ccc",
        "sha256:aaa",
    ]


def test_deposits_are_listed_as_a_set_of_bindings(client: TestClient) -> None:
    """The reason the wire carries a list and not a doi field."""
    seal("sha256:aaa")
    deposit("sha256:aaa")
    deposit("sha256:aaa", archive="dataverse", identifier="hdl:1902.1/1")

    body = client.get("/api/v1/ree-index").json()

    bindings = body["items"][0]["archive_attestations"]
    assert {b["archive"] for b in bindings} == {"zenodo", "dataverse"}


def test_deposited_only_hides_local_seals(client: TestClient) -> None:
    seal("sha256:aaa")
    seal("sha256:bbb")
    deposit("sha256:bbb")

    body = client.get("/api/v1/ree-index", params={"deposited_only": "true"}).json()

    assert [item["subject_digest"] for item in body["items"]] == ["sha256:bbb"]


def test_pagination_walks_every_entry_exactly_once(client: TestClient) -> None:
    for index in range(5):
        seal(f"sha256:{index}", sealed_at=f"2026-07-2{index}T00:00:00Z")

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        body = client.get("/api/v1/ree-index", params=params).json()
        seen.extend(item["subject_digest"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == [f"sha256:{index}" for index in reversed(range(5))]


def test_a_malformed_cursor_is_a_client_error(client: TestClient) -> None:
    resp = client.get("/api/v1/ree-index", params={"cursor": "nonsense"})

    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "invalid_cursor"
