from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_agent.config as config_module


def test_load_config_prefers_explicit_agent_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_AGENT_ID", "agent-explicit")
    monkeypatch.setenv("WORKBENCH_API_WS_URL", "wss://api.example/agent/connect")
    monkeypatch.setenv("WORKBENCH_DOCKER_MODE", "host-socket")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    config = config_module.load_config()

    assert config.agent_id == "agent-explicit"
    assert config.api_ws_url == "wss://api.example/agent/connect"
    assert config.docker.mode == "host-socket"
    assert config.otlp_endpoint == "http://collector:4318"


def test_load_config_persists_identity_when_not_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WORKBENCH_AGENT_ID", raising=False)
    monkeypatch.delenv("OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("WORKBENCH_AGENT_STATE_DIR", str(tmp_path))
    paths: list[Path] = []

    def load_identity(path: Path) -> str:
        paths.append(path)
        return "persisted-agent"

    monkeypatch.setattr(
        config_module,
        "load_or_create_agent_id",
        load_identity,
    )

    config = config_module.load_config()

    assert config.agent_id == "persisted-agent"
    assert config.api_ws_url == "ws://localhost:8000/agent/connect"
    assert config.docker.mode == "dind"
    assert config.otlp_endpoint is None
    assert paths == [tmp_path]
