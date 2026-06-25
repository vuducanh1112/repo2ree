from __future__ import annotations

import pytest

import repo2ree_supervisor.manager as manager_mod
from repo2ree_supervisor import WorkbenchManager, WorkbenchRegistry


def test_dind_mode_uses_per_ree_docker_daemon(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_calls: list[tuple[str, ...]] = []
    exec_calls: list[tuple[str, ...]] = []
    silent_calls: list[tuple[str, ...]] = []

    def fake_docker(*args: str, timeout: int = 60) -> None:
        docker_calls.append(args)

    def fake_docker_exec(container: str, *argv: str) -> None:
        exec_calls.append((container, *argv))

    def fake_docker_silent(*args: str) -> None:
        silent_calls.append(args)

    monkeypatch.setattr(manager_mod, "_docker", fake_docker)
    monkeypatch.setattr(manager_mod, "_docker_exec", fake_docker_exec)
    monkeypatch.setattr(manager_mod, "_docker_silent", fake_docker_silent)

    manager = WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="repo2ree-workbench:test",
    )

    handle = manager.provision("ree123", name="Test REE")
    run_call = _only_run_call(docker_calls)

    assert ("volume", "create", "repo2ree-ree-ree123") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree123") in docker_calls
    assert "--privileged" in run_call
    assert _has_option_value(run_call, "-e", "DOCKER_DRIVER=overlay2")
    assert _has_option_value(run_call, "-v", "repo2ree-dind-ree123:/var/lib/docker")
    assert not _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")
    assert exec_calls == [
        (
            "repo2ree-wb-ree123",
            "repo2ree-exec",
            "init-ree",
            "--ree-id",
            "ree123",
            "--name",
            "Test REE",
        )
    ]

    manager.teardown(handle)

    assert ("volume", "rm", "repo2ree-ree-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree123") in silent_calls


def test_host_socket_mode_reuses_host_daemon_without_dind_volume(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_calls: list[tuple[str, ...]] = []
    silent_calls: list[tuple[str, ...]] = []

    def fake_docker(*args: str, timeout: int = 60) -> None:
        docker_calls.append(args)

    def fake_docker_silent(*args: str) -> None:
        silent_calls.append(args)

    monkeypatch.setattr(manager_mod, "_docker", fake_docker)
    monkeypatch.setattr(manager_mod, "_docker_exec", lambda container, *argv: None)
    monkeypatch.setattr(manager_mod, "_docker_silent", fake_docker_silent)

    manager = WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="repo2ree-workbench:test",
        workbench_docker_mode="host-socket",
    )

    handle = manager.provision("ree456", name="Fast REE")
    run_call = _only_run_call(docker_calls)

    assert ("volume", "create", "repo2ree-ree-ree456") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree456") not in docker_calls
    assert "--privileged" not in run_call
    assert not _has_option_value(run_call, "-e", "DOCKER_DRIVER=overlay2")
    assert not _has_option_value(run_call, "-v", "repo2ree-dind-ree456:/var/lib/docker")
    assert _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "DOCKER_HOST=unix:///var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "WORKBENCH_DOCKER_MODE=host-socket")

    manager.teardown(handle)

    assert ("volume", "rm", "repo2ree-ree-ree456") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree456") not in silent_calls


def test_invalid_workbench_docker_mode_fails_early(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown workbench docker mode"):
        WorkbenchManager(
            registry=WorkbenchRegistry(tmp_path / "registry.json"),
            workbench_image="repo2ree-workbench:test",
            workbench_docker_mode="sideways",
        )


def _only_run_call(calls: list[tuple[str, ...]]) -> tuple[str, ...]:
    run_calls = [call for call in calls if call[:2] == ("run", "-d")]
    assert len(run_calls) == 1
    return run_calls[0]


def _has_option_value(call: tuple[str, ...], option: str, value: str) -> bool:
    return any(current == option and next_value == value for current, next_value in zip(call, call[1:], strict=False))
