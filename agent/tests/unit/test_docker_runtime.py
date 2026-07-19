from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

import repo2ree_agent.docker_runtime as rt_mod
from repo2ree_agent.docker_runtime import DockerRuntime
from repo2ree_protocol.agent import AgentFrame, ErrorFrame, LocationFrame, LogFrame, WorkbenchLocation


@pytest.fixture(autouse=True)
def _no_ambient_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the host's agent-image env vars from leaking into the tests."""
    monkeypatch.delenv("REPO2REE_EXEC_BUNDLE", raising=False)
    monkeypatch.delenv("REPO2REE_TOOLS_BUNDLE", raising=False)


@pytest.fixture(autouse=True)
def _instant_viable_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the startup grace window and report started benches as running.

    Tests that exercise the exits-immediately fallback override
    ``_container_running`` themselves.
    """
    monkeypatch.setattr(rt_mod, "_STARTUP_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(rt_mod, "_container_running", lambda name: True)
    monkeypatch.setattr(rt_mod, "_probe_bench", lambda name, exec_path, image: iter(()))


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


# ================================================
# Executor-bundle injection
# ================================================


def _write_bundle(root: Path, manifest: dict, store_paths: list[str]) -> str:
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "store-paths").write_text("\n".join(store_paths) + "\n")
    return str(root)


@pytest.fixture
def exec_bundle_dir(tmp_path: Path) -> str:
    return _write_bundle(
        tmp_path / "exec-bundle",
        {
            "schema_version": 1,
            "exec_path": "/nix/store/aaa-exec/bin/repo2ree-exec",
            "pause_path": "/nix/store/bbb-busybox/bin/sleep",
        },
        ["/nix/store/aaa-exec", "/nix/store/bbb-busybox"],
    )


@pytest.fixture
def tools_bundle_dir(tmp_path: Path) -> str:
    return _write_bundle(
        tmp_path / "tools-bundle",
        {
            "schema_version": 1,
            "tools": {"syft": "/nix/store/ccc-syft/bin/syft"},
            "bin_dir": "/nix/store/ddd-tools-bin/bin",
            "env": {"SSL_CERT_FILE": "/nix/store/eee-cacert/ca-bundle.crt"},
        },
        ["/nix/store/ccc-syft", "/nix/store/ddd-tools-bin"],
    )


def _mock_docker_plumbing(monkeypatch: pytest.MonkeyPatch, *, image_has_nix: bool, volume_populated: bool):
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: docker_calls.append(args))

    def fake_docker_out(*args: str, timeout: int = 60) -> str:
        docker_calls.append(args)
        return "scratch-cid"

    monkeypatch.setattr(rt_mod, "_docker_out", fake_docker_out)
    monkeypatch.setattr(rt_mod, "_docker_silent", lambda *args: docker_calls.append(args))
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))
    monkeypatch.setattr(rt_mod, "_image_has_nix", lambda image: image_has_nix)
    monkeypatch.setattr(rt_mod, "_container_path_exists", lambda cid, path: volume_populated)
    return docker_calls


def test_provision_injects_bundle_into_foreign_image(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str, tools_bundle_dir: str
) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=False)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir, tools_bundle_dir=tools_bundle_dir)
    frames = list(runtime.provision("ree1", "docker:dind"))

    location = _only_location(frames)
    # The minted location carries the bundle's absolute entry point.
    assert location.exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"

    run_call = _only_run_call(docker_calls)
    # The store volume is mounted read-only at /nix/store and the bench is kept
    # alive by the bundle's static pause binary, not the image's sleep.
    assert runtime._bundle is not None  # noqa: SLF001
    volume = runtime._bundle.volume_name  # noqa: SLF001 — content-addressed name
    assert _has_option_value(run_call, "-v", f"{volume}:/nix/store:ro")
    # The image's own default command is the bench's main process; no keep-alive
    # command is inserted, and tini reaps the exec'd process trees.
    assert run_call[-1] == "docker:dind"
    assert "--init" in run_call
    # Tool paths, the PATH farm, and TLS roots ride the bench env.
    assert _has_option_value(run_call, "-e", "REPO2REE_TOOL_SYFT=/nix/store/ccc-syft/bin/syft")
    assert _has_option_value(run_call, "-e", "REPO2REE_TOOLS_BIN=/nix/store/ddd-tools-bin/bin")
    assert _has_option_value(run_call, "-e", "SSL_CERT_FILE=/nix/store/eee-cacert/ca-bundle.crt")
    # All four closure paths were copied into the store volume.
    cp_calls = [call for call in docker_calls if call[0] == "cp" and call[1].startswith("/nix/store/")]
    assert len(cp_calls) == 4


def test_provision_skips_injection_when_image_ships_nix(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=True, volume_populated=False)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    frames = list(runtime.provision("ree1", "repo2ree-workbench:edge"))

    # Legacy path: PATH executor, plain sleep, no store mount.
    assert _only_location(frames).exec_path == "repo2ree-exec"
    run_call = _only_run_call(docker_calls)
    assert run_call[-1] == "repo2ree-workbench:edge"
    assert not any("/nix/store" in part for part in run_call)
    assert any(isinstance(f, LogFrame) and "skipping executor injection" in f.message for f in frames)


def test_populate_skipped_when_volume_already_populated(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    list(runtime.provision("ree1", "docker:dind"))
    # The sentinel was found; no closure paths were copied.
    assert not any(call[0] == "cp" and call[1].startswith("/nix/store/") for call in docker_calls)

    # A second provision short-circuits before even touching docker for the volume.
    docker_calls.clear()
    list(runtime.provision("ree2", "docker:dind"))
    assert not any(call[:2] == ("volume", "create") and call[2].startswith("repo2ree-store-") for call in docker_calls)


def test_reprovision_reports_fresh_exec_path(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    # The stored location predates injection (PATH default); the replacement
    # bench re-decides and reports the bundle entry point.
    stale = WorkbenchLocation(container_name="repo2ree-wb-ree1", volume_name="repo2ree-ree-ree1")
    frames = list(runtime.reprovision("ree1", stale, "docker:dind"))
    assert _only_location(frames).exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"


def test_misconfigured_bundle_dir_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        DockerRuntime(exec_bundle_dir=str(tmp_path / "missing-bundle"))


def test_default_command_exit_falls_back_to_pause(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)
    # First start (image default) dies within the grace window; the pause
    # rescue stays up.
    verdicts = iter([False, True])
    monkeypatch.setattr(rt_mod, "_container_running", lambda name: next(verdicts))

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    frames = list(runtime.provision("ree1", "alpine"))

    run_calls = [call for call in docker_calls if call[:2] == ("run", "-d")]
    assert len(run_calls) == 2
    assert run_calls[0][-1] == "alpine"
    assert run_calls[1][-2:] == ("/nix/store/bbb-busybox/bin/sleep", "infinity")
    # The failed attempt was removed so the retry could reuse the name.
    assert ("rm", "-f", "repo2ree-wb-ree1") in docker_calls
    assert any(isinstance(f, LogFrame) and "exited immediately" in f.message for f in frames)
    assert _only_location(frames).exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"
    # The restart policy lands only on the surviving container.
    update_calls = [call for call in docker_calls if call[0] == "update"]
    assert update_calls == [("update", "--restart", "unless-stopped", "repo2ree-wb-ree1")]


def test_bench_that_cannot_stay_up_is_an_error_frame(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)
    monkeypatch.setattr(rt_mod, "_container_running", lambda name: False)

    frames = list(DockerRuntime(exec_bundle_dir=exec_bundle_dir).provision("ree1", "broken:img"))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors and "would not stay running" in errors[0].detail
    assert not any(isinstance(f, LocationFrame) for f in frames)


# ================================================
# Bench probe (doctor)
# ================================================


# Bound before the autouse fixture replaces the module attribute, so the
# probe's own tests exercise the real implementation.
_real_probe_bench = rt_mod._probe_bench


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_doctor_exec(monkeypatch: pytest.MonkeyPatch, completed: _FakeCompleted) -> None:
    monkeypatch.setattr(rt_mod.subprocess, "run", lambda *a, **k: completed)


def test_probe_reports_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    report = {
        "ok": True,
        "docker": {"available": True, "serverVersion": "29.0"},
        "tools": {"syft": "/nix/store/x/bin/syft", "curl": None, "git": None},
    }
    _patch_doctor_exec(monkeypatch, _FakeCompleted(0, stdout=json.dumps(report)))

    logs = [f for f in _real_probe_bench("wb", "/x/repo2ree-exec", "img") if isinstance(f, LogFrame)]
    assert any("docker 29.0" in f.message and "syft" in f.message for f in logs)
    assert not any(f.level == "warn" for f in logs)


def test_probe_warns_without_docker_substrate(monkeypatch: pytest.MonkeyPatch) -> None:
    report = {"ok": True, "docker": {"available": False, "detail": "no daemon"}, "tools": {}}
    _patch_doctor_exec(monkeypatch, _FakeCompleted(0, stdout=json.dumps(report)))

    logs = [f for f in _real_probe_bench("wb", "/x/repo2ree-exec", "img") if isinstance(f, LogFrame)]
    assert any(f.level == "warn" and "no reachable docker daemon" in f.message for f in logs)


def test_probe_fails_provision_when_ree_not_writable(monkeypatch: pytest.MonkeyPatch) -> None:
    report = {"ok": False, "reeWritable": False, "docker": {}, "tools": {}}
    _patch_doctor_exec(monkeypatch, _FakeCompleted(0, stdout=json.dumps(report)))

    with pytest.raises(RuntimeError, match="violates the workbench contract"):
        list(_real_probe_bench("wb", "/x/repo2ree-exec", "img"))


def test_probe_fails_provision_when_executor_cannot_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_doctor_exec(monkeypatch, _FakeCompleted(126, stderr="exec format error"))

    with pytest.raises(RuntimeError, match="failed the executor probe"):
        list(_real_probe_bench("wb", "/x/repo2ree-exec", "img"))
