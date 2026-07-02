from __future__ import annotations

import subprocess
import time

import pytest

import repo2ree_agent.docker_runtime as rt_mod
from repo2ree_agent.docker_runtime import DockerRuntime
from repo2ree_protocol.agent import AgentFrame, ErrorFrame, LocationFrame, LogFrame, WorkbenchLocation


def test_dind_mode_uses_per_ree_docker_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    runtime = DockerRuntime()
    frames = list(runtime.provision("ree123", "repo2ree-workbench:test"))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree123") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree123") in docker_calls
    assert "--privileged" in run_call
    assert _has_option_value(run_call, "-e", "DOCKER_DRIVER=overlay2")
    assert _has_option_value(run_call, "-v", "repo2ree-dind-ree123:/var/lib/docker")
    assert not _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")

    # A successful provision ends with the workbench's location.
    location = _only_location(frames)
    assert location.container_name == "repo2ree-wb-ree123"
    assert location.volume_name == "repo2ree-ree-ree123"


def test_host_socket_mode_reuses_host_daemon_without_dind_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    runtime = DockerRuntime(docker_mode="host-socket")
    list(runtime.provision("ree456", "repo2ree-workbench:test"))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree456") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree456") not in docker_calls
    assert "--privileged" not in run_call
    assert _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "DOCKER_HOST=unix:///var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "WORKBENCH_DOCKER_MODE=host-socket")


def test_teardown_removes_dind_volume_only_in_dind_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    silent_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(rt_mod, "_docker_silent", lambda *args: silent_calls.append(args))

    dind = DockerRuntime()
    dind.remove("ree123", _location("ree123"))
    assert ("volume", "rm", "repo2ree-ree-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree123") in silent_calls

    silent_calls.clear()
    host = DockerRuntime(docker_mode="host-socket")
    host.remove("ree456", _location("ree456"))
    assert ("volume", "rm", "repo2ree-ree-ree456") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree456") not in silent_calls


def test_provision_falls_back_to_cached_image_when_pull_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pull failure is tolerated when the image is already present locally."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: True)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", failing_pull)

    frames = list(DockerRuntime().provision("ree-cached", "default:img"))

    # Warned about the fallback, still provisioned (ends with a location).
    assert any(isinstance(f, LogFrame) and f.level == "warn" and "using cached image" in f.message for f in frames)
    assert _only_location(frames).container_name == "repo2ree-wb-ree-cached"


def test_provision_emits_error_frame_when_pull_fails_and_image_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No local copy + failed pull is a hard failure surfaced as an error frame."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", failing_pull)

    frames = list(DockerRuntime().provision("ree-absent", "default:img"))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors and "network unreachable" in errors[0].detail
    assert not any(isinstance(f, LocationFrame) for f in frames)


def test_invalid_docker_mode_fails_early() -> None:
    with pytest.raises(ValueError, match="unknown workbench docker mode"):
        DockerRuntime(docker_mode="sideways")


def test_stream_exec_timeout_bounds_silence_not_total_time() -> None:
    # Three chunks 0.6s apart under a 1s timeout: total runtime (~1.8s) exceeds
    # the timeout, but no single silent gap does — the stream must survive.
    script = "for i in 1 2 3; do printf 'chunk%s' \"$i\"; sleep 0.6; done"
    chunks = list(rt_mod._stream_exec(["sh", "-c", script], timeout=1, what="test"))
    assert b"".join(chunks) == b"chunk1chunk2chunk3"


def test_stream_exec_times_out_when_process_goes_silent() -> None:
    # A process that produced output and then hangs must be killed after one
    # silent timeout window, not after timeout-since-start semantics.
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        list(rt_mod._stream_exec(["sh", "-c", "printf started; sleep 30"], timeout=1, what="test"))
    assert time.monotonic() - t0 < 5.0


def _location(ree_id: str) -> WorkbenchLocation:
    return WorkbenchLocation(container_name=f"repo2ree-wb-{ree_id}", volume_name=f"repo2ree-ree-{ree_id}")


def _only_location(frames: list[AgentFrame]) -> WorkbenchLocation:
    locations = [f.location for f in frames if isinstance(f, LocationFrame)]
    assert len(locations) == 1
    return locations[0]


def _only_run_call(calls: list[tuple[str, ...]]) -> tuple[str, ...]:
    run_calls = [call for call in calls if call[:2] == ("run", "-d")]
    assert len(run_calls) == 1
    return run_calls[0]


def _has_option_value(call: tuple[str, ...], option: str, value: str) -> bool:
    return any(current == option and next_value == value for current, next_value in zip(call, call[1:], strict=False))
