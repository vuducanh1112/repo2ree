"""Which runner an executor uses, as its workbench chose."""

from __future__ import annotations

import json

import pytest

from repo2ree_core.execution import runners
from repo2ree_core.execution.runners import RUNNER_VARIABLE, ContainerScriptRunner, LocalScriptRunner, current_runner


@pytest.fixture(autouse=True)
def _fresh() -> None:
    runners.current_runner.cache_clear()


def test_told_nothing_the_script_runs_on_the_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RUNNER_VARIABLE, raising=False)
    assert isinstance(current_runner(), LocalScriptRunner)


def test_a_container_workbench_runs_the_ree_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        RUNNER_VARIABLE,
        json.dumps({"backend": "container", "engine": "podman", "image": "python:3.12", "script_engine": "socket"}),
    )
    runner = current_runner()
    assert isinstance(runner, ContainerScriptRunner)
    assert (runner.engine, runner.image, runner.script_engine) == ("podman", "python:3.12", "socket")


def test_a_container_workbench_refuses_an_ree_that_declares_no_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RUNNER_VARIABLE, json.dumps({"backend": "container"}))
    with pytest.raises(RuntimeError, match="declares no image"):
        current_runner()


def test_a_workbench_refusal_stops_the_script_with_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RUNNER_VARIABLE, json.dumps({"backend": "host", "refused": "cannot run them in python:3.12"}))
    with pytest.raises(RuntimeError, match=r"cannot run them in python:3\.12"):
        current_runner()
