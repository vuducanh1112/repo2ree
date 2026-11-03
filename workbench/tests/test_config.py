from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_workbench.config as config_module

STORE = ["--store", "lab=/srv/rees"]


def test_load_config_prefers_explicit_workbench_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    opaque = "test-store-token"
    monkeypatch.setenv("WORKBENCH_ID", "workbench-explicit")
    monkeypatch.setenv("WORKBENCH_API_WS_URL", "wss://api.example/workbench/connect")
    monkeypatch.setenv("WORKBENCH_AUTH_TOKEN", opaque)
    monkeypatch.setenv("WORKBENCH_STORE", "lab-1=/srv/rees")
    monkeypatch.setenv("REPO2REE_EXEC_PATH", "/bin/repo2ree-exec")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    config = config_module.load_config()

    assert config.workbench_id == "workbench-explicit"
    assert config.api_ws_url == "wss://api.example/workbench/connect"
    assert config.enrollment_token == opaque
    assert (config.store_id, config.store_root) == ("lab-1", Path("/srv/rees"))
    assert config.exec_path == "/bin/repo2ree-exec"
    assert config.otlp_endpoint == "http://collector:4318"


def test_load_config_persists_identity_when_not_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WORKBENCH_ID", raising=False)
    monkeypatch.delenv("OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("WORKBENCH_STATE_DIR", str(tmp_path))
    paths: list[Path] = []

    def load_identity(path: Path) -> str:
        paths.append(path)
        return "persisted-workbench"

    monkeypatch.setattr(config_module, "load_or_create_workbench_id", load_identity)

    config = config_module.load_config(STORE)

    assert config.workbench_id == "persisted-workbench"
    assert config.api_ws_url == "ws://localhost:8000/workbench/connect"
    assert config.enrollment_token == ""
    assert config.otlp_endpoint is None
    assert paths == [tmp_path]


def test_a_workbench_serves_a_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_ID", "workbench-1")
    monkeypatch.delenv("WORKBENCH_STORE", raising=False)

    with pytest.raises(SystemExit):
        config_module.load_config([])
    with pytest.raises(SystemExit):
        config_module.load_config(["--store", "no-path"])


# ================================================
# Telemetry destination
# ================================================


def _clear_telemetry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("WORKBENCH_TELEMETRY", "OTLP_ENDPOINT", "TRACE_FILE", "WORKBENCH_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WORKBENCH_ID", "workbench-1")


def test_a_reachable_collector_is_exported_to(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_telemetry_env(monkeypatch)
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    assert config_module.load_config(STORE).telemetry == "direct"


def test_a_trace_file_keeps_spans_on_the_machine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_telemetry_env(monkeypatch)
    monkeypatch.setenv("TRACE_FILE", str(tmp_path / "spans.jsonl"))

    assert config_module.load_config(STORE).telemetry == "local"


def test_a_store_workbench_stays_silent_rather_than_relaying(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_telemetry_env(monkeypatch)

    # Possibly someone else's machine. It does not start shipping its own telemetry
    # across that boundary merely because nobody configured a collector.
    assert config_module.load_config(STORE).telemetry == "off"


def test_an_explicit_setting_overrides_every_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_telemetry_env(monkeypatch)
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("WORKBENCH_TELEMETRY", "relay")

    # The operator's escape hatch, either way: relay over the socket, or emit nothing.
    assert config_module.load_config(STORE).telemetry == "relay"


def test_an_unknown_setting_names_the_modes_it_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_telemetry_env(monkeypatch)
    monkeypatch.setenv("WORKBENCH_TELEMETRY", "collector")

    with pytest.raises(ValueError, match="direct, relay, local, off"):
        config_module.load_config(STORE)


# ================================================
# Images a store offers
# ================================================


def test_a_container_store_offers_its_images_the_first_its_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_ID", "wb-store")
    offered = ["--image", "python:3.12", "--image", "docker:29", "--image", "python:3.12"]

    config = config_module.load_config([*STORE, "--backend", "container", *offered])

    assert config.images == ("python:3.12", "docker:29")


def test_only_a_container_store_offers_images(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_ID", "wb-store")

    with pytest.raises(SystemExit):
        config_module.load_config([*STORE, "--image", "python:3.12"])
