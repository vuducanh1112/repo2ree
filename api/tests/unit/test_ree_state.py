from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ree_definitions import ree_definition

from repo2ree_api.deps import command_dispatcher
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_ree.model import Ree, ReeSubject
from repo2ree_supervisor import ReeRoute


def test_ree_state_omits_inline_content_and_exposes_placement(
    client: TestClient,
    online_ree: ReeRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ree = Ree(subject=ReeSubject(definition=ree_definition(name="demo")))
    workspace = WorkbenchReeDocument.model_validate(
        {
            "ree": ree.model_dump(mode="json"),
            "status": "draft",
            "audit": audit(ree).model_dump(mode="json"),
            "steps": ree_steps(ree, audit(ree)).model_dump(mode="json"),
            "workspace_files": [
                {"path": "ree-scripts/build_experiment_environment.sh", "kind": "generated", "size": 12}
            ],
            "ree_files": [{"path": "artifacts/sbom.json", "tag": "Artifact", "size": 34}],
        }
    )
    monkeypatch.setattr(command_dispatcher, "get_ree_state", lambda handle: workspace)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/state")

    assert resp.status_code == 200
    state = resp.json()
    assert state["ree_id"] == online_ree.ree_id
    assert state["workbench"]["status"] == "available"
    assert "build" in state["workbench"]
    assert "executor_build" in state["workbench"]
    assert state["workspace_files"] == [
        {"path": "ree-scripts/build_experiment_environment.sh", "kind": "generated", "size": 12, "content": None}
    ]
    assert state["ree_files"] == [
        {"path": "artifacts/sbom.json", "kind": "ree", "tag": "Artifact", "size": 34, "content": None}
    ]
    assert "draft_manifest" not in state
