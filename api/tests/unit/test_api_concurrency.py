"""Optimistic concurrency at the HTTP authoring boundary."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_protocol import ActionResult
from repo2ree_supervisor import WorkbenchHandle


def _etag(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def test_intent_version_conflict_reports_expected_and_actual_versions(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workbench_manager, "get_ree_metadata", lambda handle: {"updatedAt": "v2"})

    resp = client.patch(
        f"/api/v1/rees/{online_ree.ree_id}/intent",
        json={"reeIntentPatch": {"name": "changed"}, "expectedVersion": "v1"},
    )

    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["retryable"] is True
    assert error["details"] == {"expectedVersion": "v1", "actualVersion": "v2"}


def test_file_write_rejects_stale_etag(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workbench_manager, "read_file_bytes", lambda handle, path: b"current")

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        json={"path": "build.sh", "content": "next", "ifMatch": _etag(b"old")},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["actualVersion"] == _etag(b"current")


def test_file_write_returns_new_content_etag(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workbench_manager, "read_file_bytes", lambda handle, path: b"current")
    monkeypatch.setattr(
        workbench_manager,
        "dispatch_action",
        lambda handle, command, run_id, log: ActionResult(status="succeeded", exit_code=0),
    )

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        json={"path": "build.sh", "content": "next", "ifMatch": _etag(b"current")},
    )

    assert resp.status_code == 200
    assert resp.json()["etag"] == _etag(b"next")
