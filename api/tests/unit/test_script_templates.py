"""The script-template catalog endpoint (GET /api/v1/script-templates)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)
from repo2ree_core.reserved_templates import verify_templates


def test_list_script_templates_returns_catalog(client: TestClient) -> None:
    resp = client.get("/api/v1/script-templates")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Build and activation carry the seeded reserved paths and real content.
    assert body["build"]["path"] == RESERVED_BUILD_SCRIPT
    assert body["build"]["body"].startswith("#!/usr/bin/env sh")
    assert body["activation"]["runScriptPath"] == RESERVED_ACTIVATION_SCRIPT
    assert body["activation"]["verifyScriptPath"] == RESERVED_ACTIVATION_VERIFY_SCRIPT
    assert body["activation"]["runScript"].startswith("#!/usr/bin/env sh")

    # Experiment templates state the path convention and a run starter.
    experiment = body["experiment"]
    assert experiment["runScriptPathPattern"] == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh"
    assert experiment["verifyScriptPathPattern"] == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh"
    assert experiment["runScript"].startswith("#!/usr/bin/env sh")

    # The verify templates mirror the packaged registry, default first.
    assert [entry["key"] for entry in body["verify"]] == [t.key for t in verify_templates()]
    for entry in body["verify"]:
        assert entry["label"]
        assert entry["description"]
        assert entry["body"].startswith("#!/usr/bin/env sh")
        assert "set -eu" in entry["body"]
