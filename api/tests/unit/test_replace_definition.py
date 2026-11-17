"""PUT /definition sends every portable definition field as one replacement."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from ree_definitions import bare_ree

from repo2ree_api.deps import command_dispatcher
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import ReeDefinition
from repo2ree_supervisor import ReeRoute


def test_replace_definition_route_dispatches_every_definition_field(
    client: TestClient,
    online_ree: ReeRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[Any] = []

    def _dispatch(handle, command, run_id, log):
        dispatched.append(command)
        return ActionResult(status="succeeded", exit_code=0)

    ree = bare_ree()
    document = WorkbenchReeDocument(ree=ree, status="draft", audit=audit(ree), steps=ree_steps(ree, audit(ree)))
    monkeypatch.setattr(command_dispatcher, "get_ree_document", lambda handle: document)
    monkeypatch.setattr(command_dispatcher, "dispatch_action", _dispatch)

    response = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/definition",
        json={"definition": ree.subject.definition.model_copy(update={"name": "demo-renamed"}).model_dump(mode="json")},
    )

    assert response.status_code == 200, response.text
    assert set(dispatched[0].args.patch) == set(ReeDefinition.model_fields)
