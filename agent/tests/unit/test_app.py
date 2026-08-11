from __future__ import annotations

import pytest

import repo2ree_agent.app as app_module
from repo2ree_agent.config import AgentConfig, DockerConfig


def test_main_composes_telemetry_runtime_and_control_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AgentConfig(
        api_ws_url="wss://control.example/agent/connect",
        agent_id="agent-1",
        docker=DockerConfig(mode="host-socket"),
        otlp_endpoint="http://collector:4318",
    )
    shutdowns: list[str] = []
    run_args: list[object] = []

    class Provider:
        def __init__(self, name: str) -> None:
            self.name = name

        def shutdown(self) -> None:
            shutdowns.append(self.name)

    class Runtime:
        runtime_name = "docker"

    monkeypatch.setattr(app_module, "load_config", lambda: config)
    monkeypatch.setattr(app_module, "setup_logs", lambda *args, **kwargs: Provider("logs"))
    monkeypatch.setattr(app_module, "setup_tracing", lambda *args, **kwargs: Provider("traces"))
    monkeypatch.setattr(app_module, "setup_metrics", lambda *args, **kwargs: Provider("metrics"))
    monkeypatch.setattr(app_module, "otlp_log_handler", lambda provider: object())
    monkeypatch.setattr(app_module, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(app_module, "DockerRuntime", lambda mode: Runtime())

    async def run_agent(*args: object, **kwargs: object) -> None:
        run_args.extend([*args, kwargs])

    monkeypatch.setattr(app_module, "run_agent", run_agent)

    app_module.main()

    assert run_args[0] == config.api_ws_url
    assert run_args[2] == config.agent_id
    assert run_args[3] == {"docker_mode": "host-socket"}
    assert shutdowns == ["traces", "metrics", "logs"]
