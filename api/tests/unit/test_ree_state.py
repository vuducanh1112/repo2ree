"""Compact REE state for low-noise automation observation."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_supervisor import WorkbenchHandle


def test_ree_state_omits_inline_content_and_exposes_placement(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace: dict[str, Any] = {
        "reeId": online_ree.ree_id,
        "name": "demo",
        "status": "draft",
        "updatedAt": "v1",
        "reeIntent": {"name": "demo"},
        "reeSession": {},
        "consistency": {"steps": []},
        "files": [{"path": "ree/build_script.sh", "kind": "generated", "size": 12}],
        "source": None,
    }
    monkeypatch.setattr(workbench_manager, "get_workspace_state", lambda handle: workspace)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/state")

    assert resp.status_code == 200
    state = resp.json()
    assert state["reeId"] == online_ree.ree_id
    assert state["workbench"]["status"] == "available"
    assert state["files"] == [{"path": "ree/build_script.sh", "kind": "generated", "size": 12}]
    assert all("content" not in file for file in state["files"])
    assert "reeFiles" not in state
    assert "draftManifest" not in state
