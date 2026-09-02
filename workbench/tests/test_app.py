from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_workbench.app as app_module
from repo2ree_workbench.config import WorkbenchConfig


def test_main_composes_telemetry_runtime_and_control_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    opaque_enrollment = "test-enrollment-value"
    config = WorkbenchConfig(
        api_ws_url="wss://control.example/workbench/connect",
        workbench_id="workbench-1",
        allocation_id="alloc-1",
        enrollment_token=opaque_enrollment,
        root=Path("/ree"),
        exec_path="/bin/repo2ree-exec",
        substrate="docker-nested",
        otlp_endpoint="http://collector:4318",
    )
    shutdowns: list[str] = []
    workbench_args: list[object] = []

    class Provider:
        def __init__(self, name: str) -> None:
            self.name = name

        def shutdown(self) -> None:
            shutdowns.append(self.name)

    monkeypatch.setattr(app_module, "load_config", lambda: config)
    monkeypatch.setattr(app_module, "setup_logs", lambda *args, **kwargs: Provider("logs"))
    monkeypatch.setattr(app_module, "setup_tracing", lambda *args, **kwargs: Provider("traces"))
    monkeypatch.setattr(app_module, "setup_metrics", lambda *args, **kwargs: Provider("metrics"))
    monkeypatch.setattr(app_module, "otlp_log_handler", lambda provider: object())
    monkeypatch.setattr(app_module, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(app_module, "LocalExecutor", lambda *args: object())

    async def run_workbench(*args: object, **kwargs: object) -> None:
        workbench_args.extend([*args, kwargs])

    monkeypatch.setattr(app_module, "run_workbench", run_workbench)

    app_module.main()

    assert workbench_args[0] == config.api_ws_url
    assert workbench_args[2] == config.workbench_id
    kwargs = workbench_args[3]
    assert isinstance(kwargs, dict)
    assert kwargs["mode"] == "managed"
    assert kwargs["allocation_id"] == "alloc-1"
    assert kwargs["enrollment_token"] == opaque_enrollment
    assert kwargs["substrate"] == "docker-nested"
    assert shutdowns == ["traces", "metrics", "logs"]
