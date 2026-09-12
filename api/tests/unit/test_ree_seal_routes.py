from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.authoring import seal as seal_routes
from repo2ree_api.deps import workbench_manager
from repo2ree_protocol import ActionResult
from repo2ree_protocol.command import SealReeCommand
from repo2ree_supervisor import WorkbenchHandle


def test_seal_runs_in_background_and_relays_progress(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    indexed: list[tuple[str, dict[str, Any]]] = []

    def dispatch_action(handle: WorkbenchHandle, command: Any, run_id: str, log: Any) -> ActionResult:
        assert isinstance(command, SealReeCommand)
        log("system", "info", "Preparing sealed artifacts: 5/10 bytes (50%), 1/2 entries")
        return ActionResult(status="succeeded", outputs={"ree_digest": "sha256:value"})

    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch_action)
    monkeypatch.setattr(workbench_manager, "get_ree_document", lambda _handle: {"ree": {}})
    monkeypatch.setattr(
        seal_routes,
        "_record_in_ree_index",
        lambda ree_id, document: indexed.append((ree_id, document)),
    )

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/ree:seal",
        json={"include_source": True, "include_runtime": False, "include_results": True},
    )

    assert response.status_code == 200, response.text
    started = response.json()
    assert started["operation"] == "seal"
    deadline = time.monotonic() + 10
    run = started
    while run["status"] not in {"succeeded", "failed", "canceled"} and time.monotonic() < deadline:
        run = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{started['run_id']}").json()
        time.sleep(0.01)

    assert run["status"] == "succeeded"
    logs = client.get(f"/api/v1/rees/{online_ree.ree_id}/runs/{started['run_id']}/logs").json()
    assert any("Preparing sealed artifacts" in entry["message"] for entry in logs["entries"])
    assert indexed == [(online_ree.ree_id, {"ree": {}})]
