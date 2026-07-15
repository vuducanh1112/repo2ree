"""PUT /intent must be a true replace even though it rides the patch command.

The route sends the full ReeIntent dump as a top-level patch; that is only a
replace because model_dump() emits every field (defaults included) and
apply_patch merges at the top level. These tests pin both halves of that
invariant.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_protocol import ActionResult
from repo2ree_supervisor import WorkbenchHandle


def test_replace_intent_resets_fields_omitted_from_the_new_intent() -> None:
    old = ReeIntent(name="demo", swhid="swh:1:rev:abc", revision="v1.2.3")
    new = ReeIntent(name="demo-renamed")

    replaced = old.apply_patch(new.model_dump(mode="json"))

    assert replaced == new
    assert replaced.swhid == ""
    assert replaced.revision == ""


def test_replace_intent_route_patches_every_intent_field(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: list[Any] = []

    def _dispatch(handle, command, run_id, log):
        dispatched.append(command)
        return ActionResult(status="succeeded", exit_code=0)

    workspace = {
        "reeId": online_ree.ree_id,
        "name": "demo",
        "status": "draft",
        "createdAt": "t1",
        "updatedAt": "t2",
    }
    monkeypatch.setattr(workbench_manager, "get_ree_metadata", lambda handle: {"updatedAt": "t2"})
    monkeypatch.setattr(workbench_manager, "get_workspace", lambda handle: workspace)
    monkeypatch.setattr(workbench_manager, "dispatch_action", _dispatch)

    resp = client.put(
        f"/api/v1/rees/{online_ree.ree_id}/intent",
        json={"reeIntent": {"name": "demo-renamed"}},
    )

    assert resp.status_code == 200, resp.text
    # A partial patch here would silently keep fields the new intent omitted.
    assert set(dispatched[0].args.patch) == set(ReeIntent.model_fields)
