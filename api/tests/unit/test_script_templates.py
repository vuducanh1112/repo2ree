"""The script-template catalog endpoint (GET /api/v1/script-templates)."""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

from repo2ree_authoring.templates import (
    activation_templates,
    build_templates,
    experiment_run_templates,
    verify_templates,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)


def _assert_entries_match(entries: list[dict[str, Any]], expected_keys: list[str]) -> None:
    assert [entry["key"] for entry in entries] == expected_keys
    # Each environment has exactly one explicit default: its first entry, per
    # the core catalogs' ordering.
    first: dict[str | None, str] = {}
    for entry in entries:
        first.setdefault(entry["workbench_environment"], entry["key"])
    assert [entry["is_default"] for entry in entries] == [
        first[entry["workbench_environment"]] == entry["key"] for entry in entries
    ]
    for entry in entries:
        assert entry["label"]
        assert entry["description"]
        assert entry["body"].startswith("#!/usr/bin/env sh")
        assert "set -eu" in entry["body"]


def test_list_script_templates_returns_catalog(client: TestClient) -> None:
    resp = client.get("/api/v1/script-templates")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Build and activation carry the seeded reserved paths and their named
    # template variants (docker first, as the default a fresh REE is seeded with).
    assert body["build"]["path"] == RESERVED_BUILD_SCRIPT
    _assert_entries_match(body["build"]["templates"], [t.key for t in build_templates()])
    assert body["build"]["templates"][0]["key"] == "docker"
    assert body["activation"]["run_script_path"] == RESERVED_ACTIVATION_SCRIPT
    assert body["activation"]["verify_script_path"] == RESERVED_ACTIVATION_VERIFY_SCRIPT
    _assert_entries_match(body["activation"]["templates"], [t.key for t in activation_templates()])
    assert body["activation"]["templates"][0]["key"] == "docker"

    # Experiment templates state the path convention and the run variants.
    experiment = body["experiment"]
    assert experiment["run_script_path_pattern"] == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh"
    assert experiment["verify_script_path_pattern"] == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh"
    _assert_entries_match(experiment["templates"], [t.key for t in experiment_run_templates()])
    assert experiment["templates"][0]["key"] == "docker"

    # The verify templates mirror the packaged registry, default first.
    _assert_entries_match(body["verify"], [t.key for t in verify_templates()])


def test_a_host_environment_has_templates_that_need_no_container_engine(client: TestClient) -> None:
    body = client.get("/api/v1/script-templates").json()

    for section in (body["build"], body["activation"], body["experiment"]):
        [host] = [entry for entry in section["templates"] if entry["workbench_environment"] == "host"]
        assert host["is_default"]
        assert "docker" not in host["body"]


def test_the_steps_and_the_overview_name_operations_there_are(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    operations = {operation["operationId"] for path in document["paths"].values() for operation in path.values()}
    steps = client.get("/api/v1/ree-steps").json()["steps"]

    assert {action for step in steps for action in step["actions"]} <= operations
    assert set(re.findall(r"`([a-z][A-Za-z]+[A-Z][A-Za-z]+)`", document["info"]["description"])) <= operations | {
        "next_cursor",
        "upload_url",
    }
    assert "generateScriptCandidates" in document["info"]["description"]


def test_script_inference_is_how_a_step_gets_its_script(client: TestClient) -> None:
    actions = {step["key"]: step["actions"] for step in client.get("/api/v1/ree-steps").json()["steps"]}

    for step in ("build", "activation", "experiments"):
        assert "generateScriptCandidates" in actions[step]
