"""Compact REE state for low-noise automation observation."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import Ree, ReeDefinition, ReeSubject
from repo2ree_supervisor import WorkbenchHandle


def test_ree_state_omits_inline_content_and_exposes_placement(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ree = Ree(subject=ReeSubject(definition=ReeDefinition(name="demo")))
    workspace: dict[str, Any] = {
        "ree_id": online_ree.ree_id,
        "ree": ree.model_dump(mode="json"),
        "status": "draft",
        "audit": audit(ree).model_dump(mode="json"),
        "workspace_files": [{"path": "ree-scripts/build_script.sh", "kind": "generated", "size": 12}],
        "ree_files": [{"path": "artifacts/sbom.json", "tag": "Artifact", "size": 34}],
    }
    monkeypatch.setattr(workbench_manager, "get_ree_state", lambda handle: workspace)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/state")

    assert resp.status_code == 200
    state = resp.json()
    assert state["ree_id"] == online_ree.ree_id
    assert state["workbench"]["status"] == "available"
    # Typed file entries serialize every field; content stays null — never inlined.
    assert state["workspace_files"] == [
        {"path": "ree-scripts/build_script.sh", "kind": "generated", "size": 12, "content": None}
    ]
    # REE-owned evidence is part of the observation: produced files like the SBOM
    # live only under the REE root, never in the materialized workspace tree.
    assert state["ree_files"] == [
        {"path": "artifacts/sbom.json", "kind": "ree", "tag": "Artifact", "size": 34, "content": None}
    ]
    assert "draft_manifest" not in state
