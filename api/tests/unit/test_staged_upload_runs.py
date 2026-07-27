"""The contract both staged-upload routes share (see ree/upload_runs.py).

A source archive and a whole REE bundle travel the same path — claim the token,
copy the bytes in, run one command, reclaim the host copy — so the rule for what
a run reports back is pinned here once, against both routes, rather than in
either route's own file.

The staging legs are real (real routes, real staging dir); the workbench side is
stubbed, since what a command *does* with the archive is covered in the core
suite. What is under test is the control plane's bookkeeping around it.
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
from repo2ree_supervisor import WorkbenchHandle

RUN_TIMEOUT_SECONDS = 10
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})

# (init route, upload route, completing route, route-specific keys the run echoes)
UploadRoutes = tuple[str, str, str, dict[str, Any]]

_SOURCE: UploadRoutes = ("source:upload-init", "source:upload", "source:upload-complete", {"mode": "upload"})
_BUNDLE: UploadRoutes = ("ree:upload-init", "ree:upload", "ree:load", {})


def _await_run(client: TestClient, ree_id: str, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] in TERMINAL_RUN_STATUSES:
            return dict(run)
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach a terminal status within {RUN_TIMEOUT_SECONDS}s")


def _stage_and_start(
    client: TestClient,
    ree_id: str,
    routes: UploadRoutes,
    content: bytes = b"pretend-archive",
) -> dict[str, Any]:
    init_route, upload_route, complete_route, _echoed = routes
    init = client.post(
        f"/api/v1/rees/{ree_id}/{init_route}",
        json={"file_name": "archive.zip", "size": len(content), "content_type": "application/zip"},
    )
    assert init.status_code == 200, init.text
    token = init.json()["upload_token"]

    put = client.put(f"/api/v1/rees/{ree_id}/{upload_route}/{token}", content=content)
    assert put.status_code == 200, put.text

    started = client.post(
        f"/api/v1/rees/{ree_id}/{complete_route}",
        json={"upload_token": token, "archive_name": "archive.zip"},
    )
    assert started.status_code == 200, started.text
    return {"token": token, "run_id": started.json()["run_id"]}


@pytest.fixture
def stubbed_workbench(monkeypatch: pytest.MonkeyPatch) -> dict[str, ActionResult]:
    """Accept the copy; let each test choose what the command reports."""
    outcome: dict[str, ActionResult] = {}

    def copy_to_workbench(handle: WorkbenchHandle, host_path: str, container_path: str) -> None:
        return None

    def dispatch_action(handle: WorkbenchHandle, command: Any, run_id: str, log: Any) -> ActionResult:
        return outcome["result"]

    monkeypatch.setattr(workbench_manager, "copy_to_workbench", copy_to_workbench)
    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch_action)
    return outcome


@pytest.mark.parametrize("routes", [_SOURCE, _BUNDLE], ids=["source", "bundle"])
def test_failed_run_reports_both_the_request_and_what_the_command_found(
    client: TestClient,
    online_ree: WorkbenchHandle,
    staging_dir: Path,
    stubbed_workbench: dict[str, ActionResult],
    routes: UploadRoutes,
) -> None:
    """A failing command's outputs are merged over the request echo, not either alone.

    Previously the two routes disagreed: source replaced the command's outputs
    with the request echo, bundle dropped the echo and kept only the command's.
    A caller could not read both from either one.
    """
    stubbed_workbench["result"] = ActionResult.failed(
        "internal",
        "archive rejected",
        origin="executor",
        outputs={"rejected_entry": "../escape"},
    )
    _echoed = routes[3]

    started = _stage_and_start(client, online_ree.ree_id, routes)
    run = _await_run(client, online_ree.ree_id, started["run_id"])

    assert run["status"] == "failed"
    outputs = run["outputs"]
    # What the caller asked for...
    assert outputs["upload_token"] == started["token"]
    assert outputs["archive_name"] == "archive.zip"
    assert all(outputs[key] == value for key, value in _echoed.items())
    # ...and what the command found.
    assert outputs["rejected_entry"] == "../escape"


@pytest.mark.parametrize("routes", [_SOURCE, _BUNDLE], ids=["source", "bundle"])
def test_succeeded_run_reports_both_and_reclaims_the_host_copy(
    client: TestClient,
    online_ree: WorkbenchHandle,
    staging_dir: Path,
    stubbed_workbench: dict[str, ActionResult],
    routes: UploadRoutes,
) -> None:
    """The same merge rule on success — and the staged bytes are always reclaimed."""
    stubbed_workbench["result"] = ActionResult(status="succeeded", outputs={"entries": 3})

    started = _stage_and_start(client, online_ree.ree_id, routes)
    run = _await_run(client, online_ree.ree_id, started["run_id"])

    assert run["status"] == "succeeded"
    assert run["outputs"]["archive_name"] == "archive.zip"
    assert run["outputs"]["entries"] == 3
    # Ownership moved to the workbench; the control-plane landing file is gone.
    assert not staged_upload_path(started["token"]).exists()
