"""The script-template catalog endpoint (GET /api/v1/script-templates)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)
from repo2ree_core.reserved_templates import (
    activation_templates,
    build_templates,
    experiment_run_templates,
    verify_templates,
)


def _assert_entries_match(entries: list[dict[str, Any]], expected_keys: list[str]) -> None:
    assert [entry["key"] for entry in entries] == expected_keys
    # Exactly one entry per section is the explicit default: the first, per
    # the core catalogs' ordering.
    assert [entry["is_default"] for entry in entries] == [True] + [False] * (len(entries) - 1)
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
