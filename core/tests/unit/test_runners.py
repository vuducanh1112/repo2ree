"""Which runner an executor uses, as its workbench chose."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

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


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        # Docker names the id's algorithm; Podman prints the id alone.
        (f"sha256:{'a' * 64} repo@sha256:{'b' * 64}", (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}")),
        (f"{'a' * 64} repo@sha256:{'b' * 64}", (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}")),
        # An image no registry holds is known by its id.
        (f"sha256:{'a' * 64} ", (f"sha256:{'a' * 64}", f"sha256:{'a' * 64}")),
        (f"{'a' * 64} ", (f"sha256:{'a' * 64}", f"sha256:{'a' * 64}")),
        ("", None),
    ],
)
def test_an_image_is_known_by_its_id_whichever_engine_prints_it(
    monkeypatch: pytest.MonkeyPatch, printed: str, expected: tuple[str, str] | None
) -> None:
    inspected = subprocess.CompletedProcess[str]([], 0, stdout=f"{printed}\n")
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: inspected)

    assert runners._inspect("engine", "image") == expected


def test_what_a_script_wrote_goes_to_whoever_owns_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "made").mkdir(parents=True)
    stat_owner = f"{workspace.stat().st_uid}:{workspace.stat().st_gid}"
    # chown here cannot change an owner, so it stands in as one that says what it was asked.
    (tmp_path / "chown").write_text('#!/bin/sh\necho "$2" > "$3/asked"\n')
    (tmp_path / "chown").chmod(0o755)

    command = runners._hand_back_command(workspace)
    subprocess.run(command, check=True, env={"PATH": f"{tmp_path}:{os.environ['PATH']}"})

    assert (workspace / "asked").read_text().strip() == stat_owner
