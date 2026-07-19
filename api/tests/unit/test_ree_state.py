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
        "ree_id": online_ree.ree_id,
        "name": "demo",
        "status": "draft",
        "updated_at": "v1",
        "ree_intent": {"name": "demo"},
        "ree_session": {},
        "consistency": {"steps": []},
        "files": [{"path": "ree-scripts/build_script.sh", "kind": "generated", "size": 12}],
    }
    monkeypatch.setattr(workbench_manager, "get_workspace_state", lambda handle: workspace)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/state")

    assert resp.status_code == 200
    state = resp.json()
    assert state["ree_id"] == online_ree.ree_id
    assert state["workbench"]["status"] == "available"
    # Typed file entries serialize every field; content stays null — never inlined.
    assert state["files"] == [{"path": "ree-scripts/build_script.sh", "kind": "generated", "size": 12, "content": None}]
    assert "ree_files" not in state
    assert "draft_manifest" not in state
