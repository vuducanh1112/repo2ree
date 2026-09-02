"""Environment-backed provider configuration.

The contract under test: an explicit ``PROVIDER_ID`` wins outright and never
touches the state dir, an absent one falls back to the persisted identity, and
every remaining knob has a working default so a bare ``repo2ree-provider-docker``
starts against a local control plane.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_provider_docker.config as config_module

_PROVIDER_ENV = (
    "PROVIDER_ID",
    "PROVIDER_STATE_DIR",
    "PROVIDER_API_WS_URL",
    "PROVIDER_WORKBENCH_API_WS_URL",
    "PROVIDER_DOCKER_MODE",
    "PROVIDER_WORKBENCH_DOCKER_NETWORK",
    "OTLP_ENDPOINT",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


def test_load_config_prefers_explicit_provider_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("PROVIDER_API_WS_URL", "wss://api.example/provider/connect")
    monkeypatch.setenv("PROVIDER_WORKBENCH_API_WS_URL", "wss://api.example/workbench/connect")
    monkeypatch.setenv("PROVIDER_DOCKER_MODE", "host-socket")
    monkeypatch.setenv("PROVIDER_WORKBENCH_DOCKER_NETWORK", "repo2ree-lab")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    def refuse_identity(path: Path) -> str:
        raise AssertionError("an explicit provider id must not touch the state dir")

    monkeypatch.setattr(config_module, "load_or_create_provider_id", refuse_identity)

    config = config_module.load_config()

    assert config.provider_id == "docker-provider-explicit"
    assert config.api_ws_url == "wss://api.example/provider/connect"
    assert config.workbench_api_ws_url == "wss://api.example/workbench/connect"
    assert config.docker_mode == "host-socket"
    assert config.workbench_network == "repo2ree-lab"
    assert config.otlp_endpoint == "http://collector:4318"


def test_load_config_persists_identity_when_not_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVIDER_STATE_DIR", str(tmp_path))
    paths: list[Path] = []

    def load_identity(path: Path) -> str:
        paths.append(path)
        return "persisted-provider"

    monkeypatch.setattr(config_module, "load_or_create_provider_id", load_identity)

    config = config_module.load_config()

    assert config.provider_id == "persisted-provider"
    assert paths == [tmp_path]
    # The two connections are separate endpoints on the same control plane: the
    # provider dials one itself and hands the other to each workbench it starts.
    assert config.api_ws_url == "ws://localhost:8000/provider/connect"
    assert config.workbench_api_ws_url == "ws://localhost:8000/workbench/connect"
    assert config.docker_mode == "dind"
    assert config.workbench_network == ""
    assert config.otlp_endpoint is None


def test_blank_otlp_endpoint_reads_as_no_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    # Compose passes `OTLP_ENDPOINT: ${OTLP_ENDPOINT:-}`, so an unset host var
    # arrives as an empty string rather than as an absent one.
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("OTLP_ENDPOINT", "")

    assert config_module.load_config().otlp_endpoint is None
