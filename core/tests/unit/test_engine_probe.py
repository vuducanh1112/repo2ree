"""The engine probe, run for real against engines that are shell scripts on PATH."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

import pytest

from repo2ree_core.execution.engine_probe import RunnerEngineProbe, observed, parse
from repo2ree_core.execution.runners import LocalScriptRunner, ProbeResult

NO_DAEMON = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"


def _engine(directory: Path, name: str, script: str) -> None:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def engines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory first on PATH, before only what the probe itself needs."""
    directory = tmp_path / "bin"
    directory.mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool in ("sh", "tr", "head", "sleep"):
        found = shutil.which(tool)
        assert found, tool
        (tools / tool).symlink_to(found)
    monkeypatch.setenv("PATH", f"{directory}:{tools}")
    return directory


def _probe(workspace: Path, seconds: float = 10) -> RunnerEngineProbe:
    workspace.mkdir(exist_ok=True)
    return RunnerEngineProbe(workspace, runner=LocalScriptRunner, seconds=seconds)


def test_an_engine_that_answers_is_usable_and_one_that_cannot_reach_its_daemon_is_not(
    tmp_path: Path, engines: Path
) -> None:
    _engine(engines, "docker", f"echo '{NO_DAEMON}' >&2; exit 1")
    _engine(engines, "podman", "echo 'Podman Engine|5.2.0|true'")
    seen = _probe(tmp_path / "workspace").probe()
    assert seen.status == "probed"
    assert seen.runner == "host"
    docker, podman = seen.engines
    assert (docker.state, docker.detail) == ("unreachable", NO_DAEMON)
    assert docker.client_path == str(engines / "docker")
    assert (podman.state, podman.server, podman.version, podman.rootless) == ("usable", "Podman Engine", "5.2.0", True)


def test_an_engine_without_a_client_is_absent(tmp_path: Path, engines: Path) -> None:
    _engine(engines, "docker", "echo 'Docker Engine - Community|27.3.1'")
    docker, podman = _probe(tmp_path / "workspace").probe().engines
    assert (docker.state, docker.server, docker.version, docker.rootless) == (
        "usable",
        "Docker Engine - Community",
        "27.3.1",
        None,
    )
    assert podman.state == "absent"


def test_a_docker_client_served_by_podman_says_so(tmp_path: Path, engines: Path) -> None:
    _engine(engines, "docker", "echo 'Podman Engine|5.2.0'")
    docker, _ = _probe(tmp_path / "workspace").probe().engines
    assert (docker.state, docker.server) == ("usable", "Podman Engine")


def test_an_engine_that_does_not_answer_in_time_is_unreachable(tmp_path: Path, engines: Path) -> None:
    _engine(engines, "podman", "sleep 5")
    docker, podman = _probe(tmp_path / "workspace", seconds=1).probe().engines
    assert docker.state == "absent"
    assert (podman.state, podman.detail) == ("unreachable", "no answer within 1s")


def test_the_machine_is_probed_once(tmp_path: Path, engines: Path) -> None:
    counter = tmp_path / "asked"
    _engine(engines, "docker", f"echo x >> {counter}; echo 'Docker Engine - Community|27.3.1'")
    probe = _probe(tmp_path / "workspace")
    assert probe.probe() == probe.probe()
    assert counter.read_text() == "x\n"


def test_a_runner_that_refuses_leaves_the_engines_unknown(tmp_path: Path) -> None:
    def refusing() -> LocalScriptRunner:
        raise RuntimeError("this workbench runs scripts in a container, and the REE declares no image to run them in")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    seen = RunnerEngineProbe(workspace, runner=refusing).probe()
    assert (seen.status, seen.engines) == ("failed", [])
    assert "declares no image" in seen.detail


def test_a_probe_that_printed_nothing_leaves_the_engines_unknown() -> None:
    seen = observed(ProbeResult(runner="container", image="img", returncode=127, stdout="", stderr="sh: not found\n"))
    assert (seen.status, seen.detail, seen.image) == ("failed", "exit 127: sh: not found", "img")


def test_lines_the_probe_does_not_know_are_ignored() -> None:
    assert parse("noise\nkubectl\tusable\t/bin/kubectl\tx\n") == {}
