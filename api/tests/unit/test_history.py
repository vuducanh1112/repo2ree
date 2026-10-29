"""Operation records are exposed through the live workbench query."""

from typing import Any

from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.history import OperationHistory


def test_history_endpoint_includes_failed_and_pending_attempts(client, online_ree, monkeypatch):
    records: list[dict[str, Any]] = [
        {
            "attempt_id": "one",
            "run_id": "run",
            "command": {"operation": "write_file", "args": {"path": "x"}},
            "scope": ".",
            "operation_status": "failed",
            "capture_status": "captured",
            "sequence": 1,
        },
        {
            "attempt_id": "two",
            "run_id": "review",
            "command": {"operation": "review_build_runtime"},
            "scope": "reviews/r",
            "operation_status": "unknown",
            "capture_status": "pending",
        },
    ]
    monkeypatch.setattr(
        workbench_manager, "get_history", lambda handle: OperationHistory.model_validate({"operations": records})
    )
    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/history")
    assert response.status_code == 200
    assert response.json()["operations"][0]["command"] == records[0]["command"]
    assert response.json()["operations"][1]["capture_status"] == "pending"


def test_history_query_failure_returns_gateway_error(client, online_ree, monkeypatch):
    def fail(handle):
        raise RuntimeError("unreadable history")

    monkeypatch.setattr(workbench_manager, "get_history", fail)
    assert client.get(f"/api/v1/rees/{online_ree.ree_id}/history").status_code == 502
