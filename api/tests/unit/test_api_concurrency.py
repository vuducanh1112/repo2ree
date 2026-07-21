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
    monkeypatch.setattr(workbench_manager, "get_ree_metadata", lambda handle: {"updated_at": "v2"})

    resp = client.patch(
        f"/api/v1/rees/{online_ree.ree_id}/intent",
        json={"ree_intent_patch": {"name": "changed"}, "expected_version": "v1"},
    )

    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["retryable"] is True
    assert error["details"] == {"expected_version": "v1", "actual_version": "v2"}


def _conflict_result(path: str, expected: str, actual: str | None) -> ActionResult:
    """The shape the write/delete handlers report on an etag mismatch."""
    return ActionResult.failed(
        "conflict",
        f"etag mismatch for {path}",
        retryable=True,
        outputs={
            "error_code": "version_conflict",
            "path": path,
            "expected_version": expected,
            "actual_version": actual,
        },
    )


def test_file_write_conflict_from_the_workbench_maps_to_409(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = _etag(b"old")
    dispatched = []

    def _dispatch(handle, command, run_id, log):
        dispatched.append(command)
        return _conflict_result("build.sh", stale, _etag(b"current"))

    monkeypatch.setattr(workbench_manager, "dispatch_action", _dispatch)

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        json={"path": "build.sh", "content": "next", "if_match": stale},
    )

    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "version_conflict"
    assert error["retryable"] is True
    assert error["details"]["actual_version"] == _etag(b"current")
    # The guard rides inside the command so the workbench checks it atomically.
    assert dispatched[0].args.expected_etag == stale


def test_file_delete_conflict_from_the_workbench_maps_to_409(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = _etag(b"old")
    monkeypatch.setattr(
        workbench_manager,
        "dispatch_action",
        lambda handle, command, run_id, log: _conflict_result("build.sh", stale, _etag(b"current")),
    )

    resp = client.delete(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        params={"path": "build.sh", "if_match": stale},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "version_conflict"


def test_file_write_returns_new_content_etag(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workbench_manager,
        "dispatch_action",
        lambda handle, command, run_id, log: ActionResult(status="succeeded", exit_code=0),
    )

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        json={"path": "build.sh", "content": "next", "if_match": _etag(b"current")},
    )

    assert resp.status_code == 200
    assert resp.json()["etag"] == _etag(b"next")


def test_workbench_command_failure_maps_to_400_with_operation_code(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workbench_manager,
        "dispatch_action",
        lambda handle, command, run_id, log: ActionResult.failed(
            "validation", "reserved path", outputs={"reason": "reserved path"}
        ),
    )

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/files/content",
        json={"path": "build.sh", "content": "next"},
    )

    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] == "write_file_failed"
    assert error["retryable"] is False
    assert error["details"]["outputs"] == {"reason": "reserved path"}
