from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_workbench.config as config_module


def test_load_config_prefers_explicit_workbench_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    opaque_enrollment = "test-enrollment-value"
    monkeypatch.setenv("WORKBENCH_ID", "workbench-explicit")
    monkeypatch.setenv("WORKBENCH_API_WS_URL", "wss://api.example/workbench/connect")
    monkeypatch.setenv("WORKBENCH_ALLOCATION_ID", "alloc-1")
    monkeypatch.setenv("WORKBENCH_AUTH_TOKEN", opaque_enrollment)
    monkeypatch.setenv("WORKBENCH_ROOT", "/custom-ree")
    monkeypatch.setenv("REPO2REE_EXEC_PATH", "/bin/repo2ree-exec")
    monkeypatch.setenv("WORKBENCH_LOCATION_ID", "lab-1")
    monkeypatch.setenv("WORKBENCH_IMAGE", "docker.io/library/docker:29-dind")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    config = config_module.load_config()

    assert config.workbench_id == "workbench-explicit"
    assert config.api_ws_url == "wss://api.example/workbench/connect"
    assert config.allocation_id == "alloc-1"
    assert config.enrollment_token == opaque_enrollment
    assert config.root == Path("/custom-ree")
    assert config.exec_path == "/bin/repo2ree-exec"
    assert (config.location_id, config.image) == ("lab-1", "docker.io/library/docker:29-dind")
    assert config.otlp_endpoint == "http://collector:4318"


def test_load_config_persists_identity_when_not_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WORKBENCH_ID", raising=False)
    monkeypatch.delenv("OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("WORKBENCH_STATE_DIR", str(tmp_path))
    paths: list[Path] = []

    def load_identity(path: Path) -> str:
        paths.append(path)
        return "persisted-workbench"

    monkeypatch.setattr(
        config_module,
        "load_or_create_workbench_id",
        load_identity,
    )

    config = config_module.load_config()

    assert config.workbench_id == "persisted-workbench"
    assert config.api_ws_url == "ws://localhost:8000/workbench/connect"
    assert config.allocation_id == ""
    assert config.enrollment_token == ""
    assert config.root == Path("/ree")
    assert config.otlp_endpoint is None
    assert paths == [tmp_path]
