"""Shared Docker op plumbing: the metric context manager and CLI wrappers."""

from __future__ import annotations

import subprocess

import pytest

import repo2ree_docker.ops as ops_mod
from repo2ree_docker.errors import WorkbenchGoneError
from repo2ree_docker.ops import ContainerStateUnknownError, container_running, docker_op


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _capture_recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ops_mod,
        "record_docker_operation",
        lambda operation, _started_at, status: recorded.append((operation, status)),
    )
    return recorded


def test_strict_remove_rejects_unacknowledged_docker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="daemon unavailable"),
    )

    with pytest.raises(RuntimeError, match="daemon unavailable"):
        ops_mod.run_docker_remove("rm", "-f", "workbench")


def test_container_running_reports_confirmed_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed `docker inspect` is a confirmed verdict: a running or stopped
    container, or a genuinely absent one (which is a confirmed "not running")."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(0, stdout="true\n"))
    assert container_running("wb") is True

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(0, stdout="false\n"))
    assert container_running("wb") is False

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(1, stderr="Error: No such object: wb"))
    assert container_running("wb") is False


def test_container_running_raises_unknown_when_probe_cannot_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout or a daemon-unreachable error is *not* evidence the bench is
    gone — it must surface as indeterminate, never as a confirmed "not running"."""

    def _timeout(*_a: object, **_k: object) -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd="docker inspect", timeout=10)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(ContainerStateUnknownError):
        container_running("wb")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _FakeCompleted(1, stderr="Cannot connect to the Docker daemon"),
    )
    with pytest.raises(ContainerStateUnknownError):
        container_running("wb")


def test_docker_op_maps_each_exit_to_its_terminal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The context manager centralises the exit→status mapping every call site
    used to hand-roll: clean exit succeeds, a workbench-gone raise is unavailable,
    an indeterminate probe is unknown, anything else fails, and an explicit
    override (used by swallowing paths) wins."""
    recorded = _capture_recorded(monkeypatch)

    with docker_op("docker.x"):
        pass
    assert recorded[-1] == ("docker.x", "succeeded")

    with pytest.raises(RuntimeError), docker_op("docker.x"):
        raise RuntimeError("boom")
    assert recorded[-1] == ("docker.x", "failed")

    with pytest.raises(WorkbenchGoneError), docker_op("docker.x"):
        raise WorkbenchGoneError("gone")
    assert recorded[-1] == ("docker.x", "unavailable")

    with pytest.raises(ContainerStateUnknownError), docker_op("docker.x"):
        raise ContainerStateUnknownError("blip")
    assert recorded[-1] == ("docker.x", "unknown")

    with docker_op("docker.x") as op:
        op.status = "failed_ignored"
    assert recorded[-1] == ("docker.x", "failed_ignored")
