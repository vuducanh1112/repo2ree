"""Process composition for the Docker provider.

``main`` is the only place the four collaborators meet, so this asserts the
wiring rather than any behaviour they own: config reaches the isolation backend
and the capacity connection intact, and the telemetry providers it created are
shut down on the way out.
"""

from __future__ import annotations

import pytest

import repo2ree_provider_docker.app as app_module
from repo2ree_provider_docker.config import CuratedImage, ProviderConfig


class _Provider:
    def __init__(self, name: str, shutdowns: list[str]) -> None:
        self.name = name
        self._shutdowns = shutdowns

    def shutdown(self) -> None:
        self._shutdowns.append(self.name)


_CURATED = CuratedImage(
    id="standard",
    ref="registry.example/bench@sha256:" + "0" * 64,
    label="Standard Docker workbench",
    description="A fixed deployment-managed Docker workbench.",
)


def _config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "api_ws_url": "wss://control.example/provider/connect",
        "workbench_api_ws_url": "wss://control.example/workbench/connect",
        "provider_id": "docker-provider-1",
        "location_id": "lab-1",
        "location_label": "Lab 1",
        "images": (_CURATED,),
        "accepts_custom_image": False,
        "docker_mode": "host-socket",
        "workbench_network": "repo2ree-lab",
        "otlp_endpoint": "http://collector:4318",
    }
    return ProviderConfig(**{**base, **overrides})  # type: ignore[arg-type]


def _stub_telemetry(monkeypatch: pytest.MonkeyPatch, shutdowns: list[str]) -> None:
    monkeypatch.setattr(app_module, "setup_logs", lambda *args, **kwargs: _Provider("logs", shutdowns))
    monkeypatch.setattr(app_module, "setup_tracing", lambda *args, **kwargs: _Provider("traces", shutdowns))
    monkeypatch.setattr(app_module, "setup_metrics", lambda *args, **kwargs: _Provider("metrics", shutdowns))
    monkeypatch.setattr(app_module, "otlp_log_handler", lambda provider: object())
    monkeypatch.setattr(app_module, "configure_logging", lambda **kwargs: None)


def test_main_composes_telemetry_isolation_and_capacity_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    shutdowns: list[str] = []
    isolation_args: list[object] = []
    provider_args: list[object] = []
    _stub_telemetry(monkeypatch, shutdowns)

    class Isolation:
        runtime_name = "docker"

        def __init__(self, docker_mode: str, **kwargs: object) -> None:
            isolation_args.extend([docker_mode, kwargs])

    monkeypatch.setattr(app_module, "DockerIsolation", Isolation)

    async def run_provider(*args: object, **kwargs: object) -> None:
        provider_args.extend([*args, kwargs])

    monkeypatch.setattr(app_module, "run_provider", run_provider)
    monkeypatch.setattr(app_module, "load_config", lambda: config)

    app_module.main()

    # The bench dial-in URL is the *workbench* endpoint: the provider injects it
    # into each environment it creates and never speaks it itself.
    assert isolation_args[0] == "host-socket"
    assert isolation_args[1] == {
        "workbench_api_ws_url": config.workbench_api_ws_url,
        "workbench_network": "repo2ree-lab",
    }
    assert provider_args[0] == config.api_ws_url
    assert provider_args[2] == config.provider_id

    # The provider announces its location and its catalog, ref included: the
    # author is committing an REE to that image and should be able to read it.
    announced = provider_args[3]
    assert isinstance(announced, dict)
    assert announced["location_id"] == "lab-1"
    assert announced["location_label"] == "Lab 1"
    assert announced["accepts_custom_image"] is False
    (published,) = announced["images"]
    assert (published.id, published.ref, published.label) == (_CURATED.id, _CURATED.ref, _CURATED.label)
    assert shutdowns == ["traces", "metrics", "logs"]


def test_main_shuts_telemetry_down_when_the_connection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # The connection loop only returns by raising; the exporters must still be
    # flushed, or a crashed provider loses the spans explaining why it crashed.
    shutdowns: list[str] = []
    _stub_telemetry(monkeypatch, shutdowns)
    monkeypatch.setattr(app_module, "load_config", lambda: _config())

    class Isolation:
        runtime_name = "docker"

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setattr(app_module, "DockerIsolation", Isolation)

    async def run_provider(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(app_module, "run_provider", run_provider)

    with pytest.raises(KeyboardInterrupt):
        app_module.main()

    assert shutdowns == ["traces", "metrics", "logs"]
