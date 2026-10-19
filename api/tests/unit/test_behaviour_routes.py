"""The control plane serves behaviour evidence as the owners wrote it, for collectors that cannot reach its disk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.settings import service_settings


def record(seq: int, **fields: object) -> bytes:
    return json.dumps({"v": 1, "seq": seq, **fields}, separators=(",", ":"), sort_keys=True).encode() + b"\n"


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    journals = tmp_path / "journal"
    journals.mkdir()
    (journals / "api-000001.ndjson").write_bytes(
        record(1, kind="journal.opened") + record(2, kind="transition") + record(3, kind="journal.closed")
    )
    # The live epoch, caught mid-append: the torn tail is not a record yet.
    (journals / "api-000002.ndjson").write_bytes(record(1, kind="journal.opened") + record(2, kind="x") + b'{"v":1,')
    (journals / "notes.txt").write_text("not a journal")
    monkeypatch.setattr(service_settings, "BEHAVIOUR_JOURNAL_DIR", journals)
    monkeypatch.setattr(service_settings, "RUN_REGISTRY_DIR", tmp_path / "runs")
    monkeypatch.setattr(service_settings, "ALLOCATION_STORE_FILE", tmp_path / "allocations.json")
    return tmp_path


def test_journals_are_listed_with_their_last_complete_record(client: TestClient, evidence: Path) -> None:
    response = client.get("/api/v1/behaviour/journals")
    assert response.status_code == 200
    assert response.json()["journals"] == [
        {"id": "api-000001", "process": "api", "epoch": 1, "last_seq": 3},
        {"id": "api-000002", "process": "api", "epoch": 2, "last_seq": 2},
    ]
    assert client.get("/api/v1/behaviour/positions").json() == {"positions": {"api-000001": 3, "api-000002": 2}}


def test_a_journal_is_served_byte_for_byte_without_its_torn_tail(client: TestClient, evidence: Path) -> None:
    whole = client.get("/api/v1/behaviour/journals/api-000002")
    assert whole.status_code == 200
    assert whole.headers["content-type"] == "application/x-ndjson"
    assert whole.content == record(1, kind="journal.opened") + record(2, kind="x")
    assert client.get("/api/v1/behaviour/journals/api-000001", params={"after": 2}).content == record(
        3, kind="journal.closed"
    )


@pytest.mark.parametrize("journal_id", ["api-000009", "notes", "..%2Fallocations"])
def test_only_journals_can_be_read(client: TestClient, evidence: Path, journal_id: str) -> None:
    assert client.get(f"/api/v1/behaviour/journals/{journal_id}").status_code == 404


def test_persisted_state_is_served_with_the_cut_it_was_read_at(client: TestClient, evidence: Path) -> None:
    run = {"run_id": "build-1", "ree_id": "ree-1", "status": "succeeded"}
    (evidence / "runs" / "build-1").mkdir(parents=True)
    (evidence / "runs" / "build-1" / "state.json").write_text(json.dumps(run))
    allocations: dict[str, dict[str, str]] = {"allocations": {}, "placements": {}}
    (evidence / "allocations.json").write_text(json.dumps(allocations))
    response = client.get("/api/v1/behaviour/state")
    assert response.status_code == 200
    assert response.json() == {
        "cut": {"api-000001": [3, 3], "api-000002": [2, 2]},
        "runs": {"build-1": run},
        "allocations": allocations,
    }


def test_served_archives_are_listed_with_the_cut_they_were_built_at(client: TestClient, evidence: Path) -> None:
    from repo2ree_api.control.behaviour import journal_positions, record_archive

    before = journal_positions()
    (evidence / "journal" / "api-000002.ndjson").open("ab").write(b'"seq":3}\n')  # The torn tail completes.
    record_archive("ree-1", "a" * 64, 10, before)
    assert client.get("/api/v1/behaviour/archives").json() == {
        "archives": [
            {"ree_id": "ree-1", "sha256": "a" * 64, "size": 10, "cut": {"api-000001": [3, 3], "api-000002": [2, 3]}}
        ]
    }
