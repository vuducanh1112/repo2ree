"""Docker runtime lifecycle, execution, and failure handling."""

from __future__ import annotations

import io
import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

import repo2ree_agent.runtimes.docker.runtime as rt_mod
from repo2ree_agent.runtimes.docker import cli as docker_cli
from repo2ree_agent.runtimes.docker.reference import DockerWorkbenchHandle, decode_reference, encode_reference
from repo2ree_agent.runtimes.docker.runtime import DockerRuntime
from repo2ree_protocol.agent import (
    AgentFrame,
    DockerWorkbenchSpec,
    ErrorFrame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    WorkbenchRef,
    WorkbenchRefFrame,
)
from repo2ree_protocol.result import ActionResult


@pytest.fixture(autouse=True)
def _no_ambient_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the host's agent-image env vars from leaking into the tests."""
    monkeypatch.delenv("REPO2REE_EXEC_BUNDLE", raising=False)
    monkeypatch.delenv("REPO2REE_TOOLS_BUNDLE", raising=False)
    monkeypatch.delenv("REPO2REE_RESOURCE_OWNER", raising=False)


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
    frames = list(runtime.provision("ree123", _spec("repo2ree-workbench:test")))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree123") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree123") in docker_calls
    assert "--privileged" in run_call
    assert _has_option_value(run_call, "-e", "DOCKER_DRIVER=overlay2")
    assert _has_option_value(run_call, "-v", "repo2ree-dind-ree123:/var/lib/docker")
    assert not _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")

    handle = decode_reference(_only_ref(frames))
    assert handle.container_name == "repo2ree-wb-ree123"
    assert handle.volume_name == "repo2ree-ree-ree123"


def test_host_socket_mode_reuses_host_daemon_without_dind_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    runtime = DockerRuntime(docker_mode="host-socket")
    list(runtime.provision("ree456", _spec("repo2ree-workbench:test")))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree456") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree456") not in docker_calls
    assert "--privileged" not in run_call
    assert _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "DOCKER_HOST=unix:///var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "WORKBENCH_DOCKER_MODE=host-socket")


def test_resource_owner_labels_workbench_container_and_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setenv("REPO2REE_RESOURCE_OWNER", "e2e-demo-123")
    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    list(DockerRuntime().provision("ree-owned", _spec("repo2ree-workbench:test")))

    label = "repo2ree.resource-owner=e2e-demo-123"
    assert ("volume", "create", "--label", label, "repo2ree-ree-ree-owned") in docker_calls
    assert ("volume", "create", "--label", label, "repo2ree-dind-ree-owned") in docker_calls
    assert _has_option_value(_only_run_call(docker_calls), "--label", label)


def test_teardown_removes_dind_volume_only_in_dind_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    silent_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(rt_mod, "_docker_remove", lambda *args: silent_calls.append(args))

    dind = DockerRuntime()
    dind.remove(_ref("ree123"))
    # -v: the bench image's own anonymous volumes (docker:dind declares
    # /var/lib/docker and /certs) are unaddressable once the container is gone,
    # so they have to be reclaimed with it.
    assert ("rm", "-f", "-v", "repo2ree-wb-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-ree-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree123") in silent_calls

    silent_calls.clear()
    host = DockerRuntime(docker_mode="host-socket")
    host.remove(_ref("ree456"))
    assert ("volume", "rm", "repo2ree-ree-ree456") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree456") not in silent_calls


def test_strict_remove_rejects_unacknowledged_docker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="daemon unavailable"),
    )

    with pytest.raises(RuntimeError, match="daemon unavailable"):
        rt_mod._docker_remove("rm", "-f", "workbench")


def test_provision_falls_back_to_cached_image_when_pull_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pull failure is tolerated when the image is already present locally."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: True)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", failing_pull)

    frames = list(DockerRuntime().provision("ree-cached", _spec("default:img")))

    # Warned about the fallback, still provisioned (ends with a location).
    assert any(isinstance(f, LogFrame) and f.level == "warn" and "using cached image" in f.message for f in frames)
    assert decode_reference(_only_ref(frames)).container_name == "repo2ree-wb-ree-cached"


def test_provision_emits_error_frame_when_pull_fails_and_image_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No local copy + failed pull is a hard failure surfaced as an error frame."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover

    monkeypatch.setattr(rt_mod, "_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(rt_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(rt_mod, "_docker_stream_lines", failing_pull)

    frames = list(DockerRuntime().provision("ree-absent", _spec("default:img")))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors
    assert "network unreachable" in errors[0].detail
    assert not any(isinstance(f, WorkbenchRefFrame) for f in frames)


def test_invalid_docker_mode_fails_early() -> None:
    with pytest.raises(ValueError, match="unknown workbench docker mode"):
        DockerRuntime(docker_mode="sideways")


def test_stream_exec_timeout_bounds_silence_not_total_time() -> None:
    # Three chunks 0.6s apart under a 1s timeout: total runtime (~1.8s) exceeds
    # the timeout, but no single silent gap does — the stream must survive.
    script = "for i in 1 2 3; do printf 'chunk%s' \"$i\"; sleep 0.6; done"
    chunks = list(docker_cli.stream_exec(["sh", "-c", script], timeout=1, what="test"))
    assert b"".join(chunks) == b"chunk1chunk2chunk3"


def test_stream_exec_times_out_when_process_goes_silent() -> None:
    # A process that produced output and then hangs must be killed after one
    # silent timeout window, not after timeout-since-start semantics.
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        list(docker_cli.stream_exec(["sh", "-c", "printf started; sleep 30"], timeout=1, what="test"))
    assert time.monotonic() - t0 < 5.0


def _spec(image: str) -> DockerWorkbenchSpec:
    return DockerWorkbenchSpec(base_image=image)


def _ref(ree_id: str, *, exec_path: str = "repo2ree-exec") -> WorkbenchRef:
    return encode_reference(
        DockerWorkbenchHandle(
            ree_id=ree_id,
            container_name=f"repo2ree-wb-{ree_id}",
            volume_name=f"repo2ree-ree-{ree_id}",
            exec_path=exec_path,
        )
    )


def _only_ref(frames: list[AgentFrame]) -> WorkbenchRef:
    refs = [f.ref for f in frames if isinstance(f, WorkbenchRefFrame)]
    assert len(refs) == 1
    return refs[0]


def _only_run_call(calls: list[tuple[str, ...]]) -> tuple[str, ...]:
    run_calls = [call for call in calls if call[:2] == ("run", "-d")]
    assert len(run_calls) == 1
    return run_calls[0]


def _has_option_value(call: tuple[str, ...], option: str, value: str) -> bool:
    return any(current == option and next_value == value for current, next_value in itertools.pairwise(call))


# ================================================
# Executor-bundle injection
# ================================================


def _write_bundle(root: Path, manifest: dict[str, Any], store_paths: list[str]) -> str:
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
    frames = list(runtime.provision("ree1", _spec("docker:dind")))

    handle = decode_reference(_only_ref(frames))
    assert handle.exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"

    run_call = _only_run_call(docker_calls)
    # The store volume is mounted read-only at /nix/store and the bench is kept
    # alive by the bundle's static pause binary, not the image's sleep.
    assert runtime._bundle is not None
    volume = runtime._bundle.volume_name
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
    frames = list(runtime.provision("ree1", _spec("repo2ree-workbench:edge")))

    # Legacy path: PATH executor, plain sleep, no store mount.
    assert decode_reference(_only_ref(frames)).exec_path == "repo2ree-exec"
    run_call = _only_run_call(docker_calls)
    assert run_call[-1] == "repo2ree-workbench:edge"
    assert not any("/nix/store" in part for part in run_call)
    assert any(isinstance(f, LogFrame) and "skipping executor injection" in f.message for f in frames)


def test_populate_skipped_when_volume_already_populated(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    list(runtime.provision("ree1", _spec("docker:dind")))
    # The sentinel was found; no closure paths were copied.
    assert not any(call[0] == "cp" and call[1].startswith("/nix/store/") for call in docker_calls)

    # A second provision short-circuits before even touching docker for the volume.
    docker_calls.clear()
    list(runtime.provision("ree2", _spec("docker:dind")))
    assert not any(call[:2] == ("volume", "create") and call[2].startswith("repo2ree-store-") for call in docker_calls)


def test_reprovision_reports_fresh_exec_path(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)

    runtime = DockerRuntime(exec_bundle_dir=exec_bundle_dir)
    # The stored location predates injection (PATH default); the replacement
    # bench re-decides and reports the bundle entry point.
    frames = list(runtime.reprovision(_ref("ree1"), _spec("docker:dind")))
    assert decode_reference(_only_ref(frames)).exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"


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
    frames = list(runtime.provision("ree1", _spec("alpine")))

    run_calls = [call for call in docker_calls if call[:2] == ("run", "-d")]
    assert len(run_calls) == 2
    assert run_calls[0][-1] == "alpine"
    assert run_calls[1][-2:] == ("/nix/store/bbb-busybox/bin/sleep", "infinity")
    # The failed attempt was removed so the retry could reuse the name.
    assert ("rm", "-f", "-v", "repo2ree-wb-ree1") in docker_calls
    assert any(isinstance(f, LogFrame) and "exited immediately" in f.message for f in frames)
    assert decode_reference(_only_ref(frames)).exec_path == "/nix/store/aaa-exec/bin/repo2ree-exec"
    # The restart policy lands only on the surviving container.
    update_calls = [call for call in docker_calls if call[0] == "update"]
    assert update_calls == [("update", "--restart", "unless-stopped", "repo2ree-wb-ree1")]


def test_bench_that_cannot_stay_up_is_an_error_frame(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)
    monkeypatch.setattr(rt_mod, "_container_running", lambda name: False)

    frames = list(DockerRuntime(exec_bundle_dir=exec_bundle_dir).provision("ree1", _spec("broken:img")))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors
    assert "would not stay running" in errors[0].detail
    assert not any(isinstance(f, WorkbenchRefFrame) for f in frames)


# ================================================
# Bench probe (doctor)
# ================================================


# Bound before the autouse fixture replaces the module attribute, so the
# probe's own tests exercise the real implementation.
_real_probe_bench = rt_mod._probe_bench
_real_container_running = rt_mod._container_running


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_doctor_exec(monkeypatch: pytest.MonkeyPatch, completed: _FakeCompleted) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed)


def test_probe_reports_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    report = {
        "ok": True,
        "docker": {"available": True, "server_version": "29.0"},
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


# ================================================
# Liveness probe: confirmed vs. indeterminate state
# ================================================


def test_container_running_reports_confirmed_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed `docker inspect` is a confirmed verdict: a running or stopped
    container, or a genuinely absent one (which is a confirmed "not running")."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(0, stdout="true\n"))
    assert _real_container_running("wb") is True

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(0, stdout="false\n"))
    assert _real_container_running("wb") is False

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompleted(1, stderr="Error: No such object: wb"))
    assert _real_container_running("wb") is False


def test_container_running_raises_unknown_when_probe_cannot_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout or a daemon-unreachable error is *not* evidence the bench is
    gone — it must surface as indeterminate, never as a confirmed "not running"."""

    def _timeout(*_a: object, **_k: object) -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd="docker inspect", timeout=10)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(rt_mod.ContainerStateUnknownError):
        _real_container_running("wb")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _FakeCompleted(1, stderr="Cannot connect to the Docker daemon"),
    )
    with pytest.raises(rt_mod.ContainerStateUnknownError):
        _real_container_running("wb")


def test_is_running_leans_available_on_an_indeterminate_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """A liveness gate that can't reach the daemon must not declare a healthy
    bench dead — doing so fails the session's next action with a spurious
    "workbench unavailable". After a retry, an unresolved probe leans available."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def _unknown(_name: str) -> bool:
        raise rt_mod.ContainerStateUnknownError("daemon blip")

    monkeypatch.setattr(rt_mod, "_container_running", _unknown)
    assert DockerRuntime().is_running(_ref("probe")) is True


def test_is_running_reports_a_confirmed_stopped_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    """A confirmed-down verdict is passed through unchanged — leaning available
    is only for the indeterminate case, never for a bench that is really gone."""
    monkeypatch.setattr(rt_mod, "_container_running", lambda _name: False)
    assert DockerRuntime().is_running(_ref("probe")) is False


# ================================================
# Action execution
# ================================================


class _InputPipe:
    def __init__(self) -> None:
        self.value = ""
        self.closed = False

    def write(self, value: str) -> None:
        self.value += value

    def close(self) -> None:
        self.closed = True


class _ActionProcess:
    def __init__(self, *, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdin = _InputPipe()
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = returncode

    def wait(self) -> int:
        return self.returncode


def test_exec_action_streams_executor_events_and_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    result = ActionResult(status="succeeded")
    proc = _ActionProcess(
        stdout=result.model_dump_json(),
        stderr=(
            '{"type":"log","stream":"stdout","level":"info","message":"working"}\n'
            '{"type":"span","payload":"encoded-span"}\n'
        ),
    )
    popen_args: list[str] = []

    def open_process(args: list[str], **kwargs: object) -> _ActionProcess:
        popen_args.extend(args)
        return proc

    monkeypatch.setattr(subprocess, "Popen", open_process)
    monkeypatch.setattr(rt_mod, "current_traceparent", lambda: "00-trace-parent")
    recorded = _capture_recorded(monkeypatch)

    frames = list(DockerRuntime().exec_action(_ref("ree1"), '{"operation":"test"}', "run-1", {}))

    assert isinstance(frames[0], LogFrame)
    assert isinstance(frames[1], SpanFrame)
    assert frames[1].payload == "encoded-span"
    assert frames[2] == ResultFrame(result=result)
    assert proc.stdin.value == '{"operation":"test"}'
    assert proc.stdin.closed is True
    assert "TRACEPARENT=00-trace-parent" in popen_args
    assert recorded == [("exec_action", "succeeded")]


def test_exec_action_reports_invalid_result_and_container_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = _capture_recorded(monkeypatch)
    processes = iter(
        [
            _ActionProcess(stdout="not-json", returncode=9),
            _ActionProcess(stdout="", returncode=137),
        ]
    )
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: next(processes))

    failed = list(DockerRuntime().exec_action(_ref("ree1"), "{}", "run-1", {}))
    unavailable = list(DockerRuntime().exec_action(_ref("ree1"), "{}", "run-2", {}))

    assert isinstance(failed[-1], ResultFrame)
    assert failed[-1].result.status == "failed"
    assert isinstance(unavailable[-1], UnavailableFrame)
    assert recorded == [("exec_action", "failed"), ("exec_action", "unavailable")]


def test_exec_action_records_spawn_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = _capture_recorded(monkeypatch)

    def fail_spawn(*args: object, **kwargs: object) -> _ActionProcess:
        raise OSError("cannot spawn")

    monkeypatch.setattr(subprocess, "Popen", fail_spawn)

    with pytest.raises(OSError, match="cannot spawn"):
        list(DockerRuntime().exec_action(_ref("ree1"), "{}", "run-1", {}))
    assert recorded == [("exec_action", "failed")]


# ================================================
# Metric context manager (_docker_op)
# ================================================


def _capture_recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(
        rt_mod,
        "_record_docker_operation",
        lambda operation, _started_at, status: recorded.append((operation, status)),
    )
    return recorded


def test_docker_op_maps_each_exit_to_its_terminal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The context manager centralises the exit→status mapping every call site
    used to hand-roll: clean exit succeeds, a workbench-gone raise is unavailable,
    an indeterminate probe is unknown, anything else fails, and an explicit
    override (used by swallowing paths) wins."""
    recorded = _capture_recorded(monkeypatch)

    with rt_mod._docker_op("docker.x"):
        pass
    assert recorded[-1] == ("docker.x", "succeeded")

    with pytest.raises(RuntimeError), rt_mod._docker_op("docker.x"):
        raise RuntimeError("boom")
    assert recorded[-1] == ("docker.x", "failed")

    with pytest.raises(rt_mod.WorkbenchGoneError), rt_mod._docker_op("docker.x"):
        raise rt_mod.WorkbenchGoneError("gone")
    assert recorded[-1] == ("docker.x", "unavailable")

    with pytest.raises(rt_mod.ContainerStateUnknownError), rt_mod._docker_op("docker.x"):
        raise rt_mod.ContainerStateUnknownError("blip")
    assert recorded[-1] == ("docker.x", "unknown")

    with rt_mod._docker_op("docker.x") as op:
        op.status = "failed_ignored"
    assert recorded[-1] == ("docker.x", "failed_ignored")


def test_probe_helpers_record_failure_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: these helpers hard-coded "succeeded" in a finally, so a probe
    that timed out was logged as a phantom success. Routed through _docker_op,
    the timeout is now recorded as a failure."""
    recorded = _capture_recorded(monkeypatch)

    def _timeout(*_a: object, **_k: object) -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd="docker", timeout=30)

    monkeypatch.setattr(subprocess, "run", _timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        rt_mod._image_present("img")
    assert recorded[-1] == ("docker.image_inspect", "failed")

    with pytest.raises(subprocess.TimeoutExpired):
        rt_mod._container_path_exists("cid", "/x")
    assert recorded[-1] == ("docker.cp_probe_path", "failed")
