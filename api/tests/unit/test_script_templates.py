"""Where an REE stands on its steps, and its script templates, as the REE's workbench reports them."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from ree_definitions import bare_ree

from repo2ree_api.authoring.catalog import _STEP_ACTIONS
from repo2ree_api.deps import command_dispatcher
from repo2ree_authoring.templates import script_template_catalog
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import REE_STEPS, ree_steps
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_supervisor import ReeRoute


@pytest.fixture
def listed(online_ree: ReeRoute, monkeypatch: pytest.MonkeyPatch) -> ReeRoute:
    """The REE's workbench answers for a fresh REE, with the catalogs its command line prints."""
    document = WorkbenchReeDocument(
        ree=bare_ree(), status="draft", audit=audit(bare_ree()), steps=ree_steps(bare_ree(), audit(bare_ree()))
    )
    monkeypatch.setattr(command_dispatcher, "get_ree_state", lambda handle: document)
    monkeypatch.setattr(command_dispatcher, "list_script_templates", lambda handle: script_template_catalog())
    return online_ree


def test_the_templates_are_the_workbenchs(client: TestClient, listed: ReeRoute) -> None:
    resp = client.get(f"/api/v1/rees/{listed.ree_id}/script-templates")

    assert resp.status_code == 200, resp.text
    assert resp.json() == script_template_catalog().model_dump(mode="json")


def test_the_steps_and_the_overview_name_operations_there_are(client: TestClient, listed: ReeRoute) -> None:
    document = client.get("/openapi.json").json()
    operations = {operation["operationId"] for path in document["paths"].values() for operation in path.values()}
    steps = client.get(f"/api/v1/rees/{listed.ree_id}/ree-steps").json()["steps"]

    assert {action for step in steps for action in step["actions"]} <= operations
    assert set(re.findall(r"`([a-z][A-Za-z]+[A-Z][A-Za-z]+)`", document["info"]["description"])) <= operations | {
        "next_cursor",
        "upload_url",
    }
    assert "suggestScripts" in document["info"]["description"]


def test_the_steps_are_where_the_ree_stands(client: TestClient, listed: ReeRoute) -> None:
    body = client.get(f"/api/v1/rees/{listed.ree_id}/ree-steps").json()

    assert [step["key"] for step in body["steps"]] == [step.key for step in REE_STEPS]
    assert body["next"] == "source"
    statuses = {step["key"]: step["status"] for step in body["steps"]}
    assert statuses["source"] == "ready"
    assert statuses["sbom"] == "blocked"


def test_every_step_has_operations_that_advance_it() -> None:
    assert set(_STEP_ACTIONS) == {step.key for step in REE_STEPS}
    assert all(_STEP_ACTIONS.values())


def test_script_inference_is_how_a_step_gets_its_script(client: TestClient, listed: ReeRoute) -> None:
    steps = client.get(f"/api/v1/rees/{listed.ree_id}/ree-steps").json()["steps"]
    actions = {step["key"]: step["actions"] for step in steps}

    for step in ("build_experiment_environment", "experiments"):
        assert "suggestScripts" in actions[step]
    # The activation runs a script the build step authors, alone: it has nothing of its own to write.
    assert actions["activation"] == ["activateExperimentEnvironment"]


@pytest.mark.parametrize("catalog", ["ree-steps", "script-templates"])
def test_an_unknown_ree_has_no_catalog(client: TestClient, catalog: str) -> None:
    assert client.get(f"/api/v1/rees/no-such-ree/{catalog}").status_code == 404
