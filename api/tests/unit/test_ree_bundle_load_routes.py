"""The control-plane leg of loading a downloaded REE bundle into a fresh REE.

The upload legs are real (real routes, real staging dir); the workbench side —
copying the staged bundle in and dispatching ``load_ree_bundle`` — is stubbed,
since restoring the bundle is covered against a real tree in the core suite.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_api.storage.upload_staging import staged_upload_path
from repo2ree_protocol import ActionResult
from repo2ree_protocol.command import LoadReeBundleCommand
from repo2ree_supervisor import WorkbenchHandle

RUN_TIMEOUT_SECONDS = 10
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})


def _stage_bundle(client: TestClient, ree_id: str, content: bytes = b"pretend-zip-bytes") -> str:
    init = client.post(
        f"/api/v1/rees/{ree_id}/ree:upload-init",
        json={"file_name": "author.zip", "size": len(content), "content_type": "application/zip"},
    )
    assert init.status_code == 200, init.text
    token = init.json()["upload_token"]
    assert init.json()["upload_url"] == f"/api/v1/rees/{ree_id}/ree:upload/{token}"

    put = client.put(f"/api/v1/rees/{ree_id}/ree:upload/{token}", content=content)
    assert put.status_code == 200, put.text
    assert staged_upload_path(token).read_bytes() == content
    return token


def _await_run(client: TestClient, ree_id: str, run_id: str) -> dict[str, Any]:
    """Poll until the background run settles — the runner owns its own thread."""
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] in TERMINAL_RUN_STATUSES:
            return run
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach a terminal status within {RUN_TIMEOUT_SECONDS}s")


def test_load_dispatches_the_bundle_command_to_the_workbench(
    client: TestClient,
    online_ree: WorkbenchHandle,
    staging_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _stage_bundle(client, online_ree.ree_id)
    copied: dict[str, Any] = {}
    dispatched: dict[str, Any] = {}

    def copy_to_workbench(handle: WorkbenchHandle, host_path: str, container_path: str) -> None:
        copied.update({"host_path": host_path, "container_path": container_path})

    def dispatch_action(handle: WorkbenchHandle, command: Any, run_id: str, log: Any) -> ActionResult:
        dispatched["command"] = command
        return ActionResult(status="succeeded", outputs={"archive_name": "author.zip"})

    monkeypatch.setattr(workbench_manager, "copy_to_workbench", copy_to_workbench)
    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch_action)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/ree:load",
        json={"upload_token": token, "archive_name": "author.zip"},
    )

    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["operation"] == "ree-load"

    run = _await_run(client, online_ree.ree_id, summary["run_id"])
    assert run["status"] == "succeeded"
    assert run["outputs"]["archive_name"] == "author.zip"

    assert copied["container_path"] == f"/ree/upload-staging/{token}.bin"
    command = dispatched["command"]
    assert isinstance(command, LoadReeBundleCommand)
    assert command.args.upload_token == token
    # The transient host landing file is cleaned up once the workbench has it.
    assert not staged_upload_path(token).exists()


def test_load_fails_the_run_when_the_upload_never_landed(
    client: TestClient,
    online_ree: WorkbenchHandle,
    staging_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/ree:upload-init",
        json={"file_name": "author.zip", "size": 9, "content_type": "application/zip"},
    )
    token = init.json()["upload_token"]

    def dispatch_action(*args: Any, **kwargs: Any) -> ActionResult:
        raise AssertionError("no bundle to dispatch")

    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch_action)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/ree:load",
        json={"upload_token": token, "archive_name": "author.zip"},
    )

    assert response.status_code == 200, response.text
    run = _await_run(client, online_ree.ree_id, response.json()["run_id"])
    assert run["status"] == "failed"
    assert run["failure"]["category"] == "precondition"


def test_load_rejects_a_malformed_upload_token(
    client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path
) -> None:
    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/ree:load",
        json={"upload_token": "../escape", "archive_name": "author.zip"},
    )

    assert response.status_code == 400


def test_load_for_unknown_ree_is_404(client: TestClient, staging_dir: Path) -> None:
    response = client.post(
        "/api/v1/rees/nope/ree:load",
        json={"upload_token": "tok-1", "archive_name": "author.zip"},
    )

    assert response.status_code == 404
