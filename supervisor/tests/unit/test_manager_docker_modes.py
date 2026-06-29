from __future__ import annotations

import pytest

import repo2ree_supervisor.manager as manager_mod
from repo2ree_supervisor import WorkbenchManager, WorkbenchRegistry


def test_dind_mode_uses_per_ree_docker_daemon(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_calls: list[tuple[str, ...]] = []
    stream_calls: list[tuple[str, ...]] = []
    exec_calls: list[tuple[str, ...]] = []
    silent_calls: list[tuple[str, ...]] = []

    def fake_docker(*args: str, timeout: int = 60) -> None:
        docker_calls.append(args)

    def fake_docker_stream(*args: str, log=None, timeout: int = 600) -> None:
        stream_calls.append(args)

    def fake_docker_exec(container: str, *argv: str) -> None:
        exec_calls.append((container, *argv))

    def fake_docker_silent(*args: str) -> None:
        silent_calls.append(args)

    monkeypatch.setattr(manager_mod, "_docker", fake_docker)
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(manager_mod, "_docker_stream", fake_docker_stream)
    monkeypatch.setattr(manager_mod, "_docker_exec", fake_docker_exec)
    monkeypatch.setattr(manager_mod, "_docker_silent", fake_docker_silent)

    manager = WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="repo2ree-workbench:test",
    )

    handle = manager.provision("ree123", name="Test REE")
    run_call = _only_run_call(docker_calls)

    assert ("pull", "repo2ree-workbench:test") in stream_calls
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
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(manager_mod, "_docker_stream", lambda *args, log=None, timeout=600: None)
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


def test_provision_records_image_and_reprovision_reuses_it(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(manager_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(manager_mod, "_docker_stream", lambda *args, log=None, timeout=600: stream_calls.append(args))
    monkeypatch.setattr(manager_mod, "_docker_exec", lambda container, *argv: None)
    monkeypatch.setattr(manager_mod, "_docker_silent", lambda *args: None)

    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image="default:img")

    # A custom image is persisted on both the handle and the registry entry.
    handle = manager.provision("ree789", name="Custom REE", image="custom:img")
    assert handle.image == "custom:img"
    entry = registry.lookup("ree789")
    assert entry is not None and entry.image == "custom:img"
    assert manager.image_for(handle) == "custom:img"

    # Reprovision pulls the REE's own image, not the manager default.
    stream_calls.clear()
    manager.reprovision("ree789")
    assert ("pull", "custom:img") in stream_calls
    assert ("pull", "default:img") not in stream_calls


def test_provision_without_image_records_manager_default(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(manager_mod, "_docker_stream", lambda *args, log=None, timeout=600: None)
    monkeypatch.setattr(manager_mod, "_docker_exec", lambda container, *argv: None)
    monkeypatch.setattr(manager_mod, "_docker_silent", lambda *args: None)

    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image="default:img")

    handle = manager.provision("ree000", name="Default REE")
    assert handle.image == "default:img"
    entry = registry.lookup("ree000")
    assert entry is not None and entry.image == "default:img"


def test_provision_falls_back_to_cached_image_when_pull_fails(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pull failure is tolerated when the image is already present locally."""
    run_calls: list[tuple[str, ...]] = []
    log_calls: list[tuple[str, str, str]] = []

    def fake_docker(*args: str, timeout: int = 60) -> None:
        run_calls.append(args)

    def failing_pull(*args: str, log=None, timeout: int = 600) -> None:
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(manager_mod, "_docker", fake_docker)
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: True)
    monkeypatch.setattr(manager_mod, "_docker_stream", failing_pull)
    monkeypatch.setattr(manager_mod, "_docker_exec", lambda container, *argv: None)
    monkeypatch.setattr(manager_mod, "_docker_silent", lambda *args: None)

    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image="default:img")

    handle = manager.provision("ree-cached", name="Cached REE", log=lambda *entry: log_calls.append(entry))

    # Provisioning still ran the container from the cached image...
    assert handle.image == "default:img"
    assert "default:img" in _only_run_call(run_calls)
    # ...and warned about the fallback through the provided log sink.
    assert any(level == "warn" and "using cached image" in message for _, level, message in log_calls)


def test_provision_reraises_when_pull_fails_and_image_absent(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No local copy + failed pull is a hard failure, not a silent fallback."""

    def failing_pull(*args: str, log=None, timeout: int = 600) -> None:
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(manager_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(manager_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(manager_mod, "_docker_stream", failing_pull)
    monkeypatch.setattr(manager_mod, "_docker_exec", lambda container, *argv: None)
    monkeypatch.setattr(manager_mod, "_docker_silent", lambda *args: None)

    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image="default:img")

    with pytest.raises(RuntimeError, match="network unreachable"):
        manager.provision("ree-absent", name="Absent REE")


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
