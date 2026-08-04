"""PUT /definition sends every portable definition field as one replacement."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import Ree, ReeDefinition
from repo2ree_protocol import ActionResult
from repo2ree_supervisor import WorkbenchHandle


def test_replace_definition_route_dispatches_every_definition_field(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[Any] = []

    def _dispatch(handle, command, run_id, log):
        dispatched.append(command)
        return ActionResult(status="succeeded", exit_code=0)

    ree = Ree()
    document = {
        "ree_id": online_ree.ree_id,
        "ree": ree.model_dump(mode="json"),
        "status": "draft",
        "audit": audit(ree).model_dump(mode="json"),
        "workspace_files": [],
        "ree_files": [],
    }
    monkeypatch.setattr(workbench_manager, "get_ree_document", lambda handle: document)
    monkeypatch.setattr(workbench_manager, "dispatch_action", _dispatch)

    response = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/definition",
        json={"definition": {"name": "demo-renamed"}},
    )

    assert response.status_code == 200, response.text
    assert set(dispatched[0].args.patch) == set(ReeDefinition.model_fields)
