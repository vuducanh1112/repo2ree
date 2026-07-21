"""The runs endpoints over real HTTP, driven by a genuinely failing run.

``source:upload-complete`` with no staged bytes fails inside the real runner
before anything crosses the workbench boundary — which makes it the one
background run the API can execute end-to-end (start → log feed → terminal
status) with no container. The Docker-gated tier covers the succeeding twin.
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import start_background_run
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchHandle

# ================================================
# Helpers
# ================================================


RUN_TIMEOUT_SECONDS = 10
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})


def _wait_for_run(client: TestClient, ree_id: str, run_id: str) -> str:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["status"]
        if status in TERMINAL_RUN_STATUSES:
            return status
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach a terminal status within {RUN_TIMEOUT_SECONDS}s")


def _start_failing_upload_run(client: TestClient, ree_id: str) -> dict[str, Any]:
    """Complete an upload whose staged bytes were never PUT: the run fails for real."""
    resp = client.post(
        f"/api/v1/rees/{ree_id}/source:upload-complete",
        json={"upload_token": "never-staged", "archive_name": "project.zip"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def failed_run(client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path) -> dict[str, Any]:
    run = _start_failing_upload_run(client, online_ree.ree_id)
    status = _wait_for_run(client, online_ree.ree_id, run["run_id"])
    assert status == "failed"
    return run


# ================================================
# Run summary
# ================================================


def test_failed_run_summary_shape(client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]) -> None:
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{failed_run['run_id']}")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["status"] == "failed"
    assert summary["operation"] == "source"
    assert summary["ree_id"] == online_ree.ree_id
    assert summary["finished_at"] is not None
    # A failed run carries its typed failure, so a client need not read the logs
    # to learn why. This upload failed its staging precondition inside the API.
    assert summary["failure"] is not None
    assert summary["failure"]["category"] == "precondition"
    assert summary["failure"]["origin"] == "api"
    assert summary["failure"]["retryable"] is False
    # internal bookkeeping never leaks into the API shape
    assert "_next_seq" not in summary
    assert "logs" not in summary


def test_run_endpoints_for_unknown_ree_are_404(client: TestClient) -> None:
    assert client.get("/api/v1/rees/nope/runs").status_code == 404
    assert client.get("/api/v1/rees/nope/runs/run-1").status_code == 404
    assert client.get("/api/v1/rees/nope/runs/run-1/logs").status_code == 404


# ================================================
# Run listing
# ================================================


def test_list_runs_is_empty_for_ree_without_runs(client: TestClient, online_ree: WorkbenchHandle) -> None:
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs")
    assert resp.status_code == 200
    assert resp.json() == {"runs": [], "next_cursor": None}


def test_list_runs_returns_summaries_newest_first(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any], staging_dir: Path
) -> None:
    second = _start_failing_upload_run(client, online_ree.ree_id)
    _wait_for_run(client, online_ree.ree_id, second["run_id"])

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert [run["run_id"] for run in runs] == [second["run_id"], failed_run["run_id"]]
    for summary in runs:
        assert summary["operation"] == "source"
        assert summary["status"] == "failed"
        # summaries carry no log feed or internal bookkeeping
        assert "logs" not in summary
        assert "_next_seq" not in summary


def test_list_runs_pagination_walks_newest_to_oldest(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any], staging_dir: Path
) -> None:
    second = _start_failing_upload_run(client, online_ree.ree_id)
    _wait_for_run(client, online_ree.ree_id, second["run_id"])
    base = f"/api/v1/rees/{online_ree.ree_id}/runs"

    first_page = client.get(base, params={"limit": 1}).json()
    assert [run["run_id"] for run in first_page["runs"]] == [second["run_id"]]
    assert first_page["next_cursor"] is not None

    second_page = client.get(base, params={"limit": 1, "cursor": first_page["next_cursor"]}).json()
    assert [run["run_id"] for run in second_page["runs"]] == [failed_run["run_id"]]
    assert second_page["next_cursor"] is None


def test_list_runs_rejects_malformed_cursor(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs", params={"cursor": "no-separator"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_cursor"


def test_unknown_run_for_known_ree_is_404(client: TestClient, online_ree: WorkbenchHandle) -> None:
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/no-such-run")
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Run not found"


# ================================================
# Log feed + pagination
# ================================================


def test_failed_run_log_feed_carries_the_failure(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{failed_run['run_id']}/logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert logs["run_status"] == "failed"
    messages = [entry["message"] for entry in logs["entries"]]
    assert "Staged upload not found, empty, or expired" in messages
    assert logs["has_more"] is False
    assert logs["next_cursor"] == str(logs["entries"][-1]["seq"])


def test_log_pagination_walks_the_feed(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    base = f"/api/v1/rees/{online_ree.ree_id}/runs/{failed_run['run_id']}/logs"

    first = client.get(base, params={"limit": 1}).json()
    assert len(first["entries"]) == 1
    assert first["has_more"] is True
    assert first["next_cursor"] == "1"

    rest = client.get(base, params={"cursor": first["next_cursor"]}).json()
    assert rest["has_more"] is False
    assert [e["seq"] for e in first["entries"] + rest["entries"]] == list(
        range(1, len(first["entries"]) + len(rest["entries"]) + 1)
    )


def test_log_pagination_rejects_garbage_cursor(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    base = f"/api/v1/rees/{online_ree.ree_id}/runs/{failed_run['run_id']}/logs"
    resp = client.get(base, params={"cursor": "not-a-number"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "request_validation_failed"


def test_observe_terminal_run_returns_status_and_logs_after_cursor(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    run_id = failed_run["run_id"]
    first_log = client.get(
        f"/api/v1/rees/{online_ree.ree_id}/runs/{run_id}/logs",
        params={"limit": 1},
    ).json()

    resp = client.get(
        f"/api/v1/rees/{online_ree.ree_id}/runs/{run_id}/observe",
        params={"cursor": first_log["next_cursor"], "wait_seconds": 0},
    )

    assert resp.status_code == 200
    observation = resp.json()
    assert observation["run"]["status"] == "failed"
    assert all(entry["seq"] > int(first_log["next_cursor"]) for entry in observation["entries"])
    assert observation["changed"] is True


# ================================================
# Cancel
# ================================================


def test_cancel_of_terminal_run_returns_status_unchanged(
    client: TestClient, online_ree: WorkbenchHandle, failed_run: dict[str, Any]
) -> None:
    run_id = failed_run["run_id"]
    logs_before = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{run_id}/logs").json()

    resp = client.post(f"/api/v1/rees/{online_ree.ree_id}/runs/{run_id}:cancel")
    assert resp.status_code == 200
    assert resp.json() == {"status": "failed"}

    # a no-op cancel appends no "Cancel requested" log entry
    logs_after = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{run_id}/logs").json()
    assert len(logs_after["entries"]) == len(logs_before["entries"])


def test_cancel_of_active_run_signals_workbench(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canceled = Event()
    calls: list[tuple[WorkbenchHandle, str]] = []

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        canceled.wait(timeout=2.0)
        return ActionResult(status="canceled")

    def _cancel_run(handle: WorkbenchHandle, run_id: str) -> None:
        calls.append((handle, run_id))
        canceled.set()

    monkeypatch.setattr(workbench_manager, "cancel_run", _cancel_run)
    run = start_background_run(
        ree_id=online_ree.ree_id,
        operation="build",
        request_payload={},
        run_id_prefix="build",
        runner=_runner,
    )

    resp = client.post(f"/api/v1/rees/{online_ree.ree_id}/runs/{run['run_id']}:cancel")

    assert resp.status_code == 200
    assert calls == [(online_ree, run["run_id"])]
    assert resp.json()["status"] in {"canceling", "canceled"}
    logs = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{run['run_id']}/logs").json()
    assert any(entry["message"] == "Cancel requested by user" for entry in logs["entries"])
    assert _wait_for_run(client, online_ree.ree_id, run["run_id"]) == "canceled"


def test_cancel_of_unknown_run_is_404(client: TestClient, online_ree: WorkbenchHandle) -> None:
    resp = client.post(f"/api/v1/rees/{online_ree.ree_id}/runs/no-such-run:cancel")
    assert resp.status_code == 404
