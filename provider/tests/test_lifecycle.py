"""Docker isolation lifecycle and failure handling."""

from __future__ import annotations

import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

import repo2ree_provider_docker.lifecycle as lc_mod
from repo2ree_docker.ops import ContainerStateUnknownError
from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import (
    AllocationStatusFrame,
    ErrorFrame,
    Frame,
    LogFrame,
)
from repo2ree_provider_docker.injection import InjectionBundle
from repo2ree_provider_docker.lifecycle import DockerIsolation


@pytest.fixture(autouse=True)
def _no_ambient_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the host's provider-image env vars from leaking into the tests."""
    monkeypatch.delenv("REPO2REE_EXEC_BUNDLE", raising=False)
    monkeypatch.delenv("REPO2REE_TOOLS_BUNDLE", raising=False)
    monkeypatch.delenv("REPO2REE_RESOURCE_OWNER", raising=False)


@pytest.fixture(autouse=True)
def _instant_viable_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the startup grace window and report started benches as running.

    Tests that exercise the exits-immediately fallback override
    ``container_running`` themselves.
    """
    monkeypatch.setattr(lc_mod, "_STARTUP_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(lc_mod, "_allocation_image", lambda name: None)
    monkeypatch.setattr(lc_mod, "container_running", lambda name: True)
    monkeypatch.setattr(lc_mod, "_probe_bench", lambda name, exec_path, image: iter(()))
    monkeypatch.setattr(lc_mod, "_resolved_image", lambda image: image)
    monkeypatch.setattr(lc_mod, "discover", lambda image: ())
    monkeypatch.setattr(lc_mod, "write_daemon_settings", lambda container, settings: None)
    monkeypatch.setattr(lc_mod, "_bench_log_tail", lambda container, lines: "")


def test_dind_mode_uses_per_ree_docker_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    isolation = DockerIsolation()
    frames = list(_provision(isolation, "ree123", _spec("repo2ree-workbench:test")))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree123") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree123") in docker_calls
    assert "--privileged" in run_call
    assert _has_option_value(run_call, "-e", "DOCKER_DRIVER=overlay2")
    assert _has_option_value(run_call, "-v", "repo2ree-dind-ree123:/var/lib/docker")
    assert not _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")

    assert _only_status(frames).allocation_id == "ree123"


def test_host_socket_mode_reuses_host_daemon_without_dind_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    isolation = DockerIsolation(docker_mode="host-socket")
    list(_provision(isolation, "ree456", _spec("repo2ree-workbench:test")))

    run_call = _only_run_call(docker_calls)
    assert ("volume", "create", "repo2ree-ree-ree456") in docker_calls
    assert ("volume", "create", "repo2ree-dind-ree456") not in docker_calls
    assert "--privileged" not in run_call
    assert _has_option_value(run_call, "-v", "/var/run/docker.sock:/var/run/docker.sock")
    assert _has_option_value(run_call, "-e", "DOCKER_HOST=unix:///var/run/docker.sock")


def test_resource_owner_labels_workbench_container_and_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setenv("REPO2REE_RESOURCE_OWNER", "e2e-demo-123")
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    list(_provision(DockerIsolation(), "ree-owned", _spec("repo2ree-workbench:test")))

    label = "repo2ree.resource-owner=e2e-demo-123"
    assert ("volume", "create", "--label", label, "repo2ree-ree-ree-owned") in docker_calls
    assert ("volume", "create", "--label", label, "repo2ree-dind-ree-owned") in docker_calls
    assert _has_option_value(_only_run_call(docker_calls), "--label", label)


def test_teardown_removes_dind_volume_only_in_dind_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    silent_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker_remove", lambda *args: silent_calls.append(args))

    dind = DockerIsolation()
    dind.release("ree123")
    # -v: the bench image's own anonymous volumes (docker:dind declares
    # /var/lib/docker and /certs) are unaddressable once the container is gone,
    # so they have to be reclaimed with it.
    assert ("rm", "-f", "-v", "repo2ree-wb-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-ree-ree123") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree123") in silent_calls

    silent_calls.clear()
    host = DockerIsolation(docker_mode="host-socket")
    host.release("ree456")
    assert ("volume", "rm", "repo2ree-ree-ree456") in silent_calls
    assert ("volume", "rm", "repo2ree-dind-ree456") not in silent_calls


def test_provision_falls_back_to_cached_image_when_pull_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pull failure is tolerated when the image is already present locally."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: True)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", failing_pull)

    frames = list(_provision(DockerIsolation(), "ree-cached", _spec("default:img")))

    # Warned about the fallback, still provisioned (ends with a location).
    assert any(isinstance(f, LogFrame) and f.level == "warn" and "using cached image" in f.message for f in frames)
    assert _only_status(frames).allocation_id == "ree-cached"


def test_provision_emits_error_frame_when_pull_fails_and_image_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No local copy + failed pull is a hard failure surfaced as an error frame."""

    def failing_pull(*args: str, timeout: int = 600):
        raise RuntimeError("network unreachable")
        yield  # pragma: no cover

    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", failing_pull)

    frames = list(_provision(DockerIsolation(), "ree-absent", _spec("default:img")))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors
    assert "network unreachable" in errors[0].detail
    assert not any(isinstance(f, AllocationStatusFrame) for f in frames)


def test_invalid_docker_mode_fails_early() -> None:
    with pytest.raises(ValueError, match="unknown workbench docker mode"):
        DockerIsolation(docker_mode="sideways")


def _spec(image: str) -> str:
    return image


def _provision(isolation: DockerIsolation, allocation_id: str, image: str):
    allocation = AllocationRequest(
        allocation_id=allocation_id,
        ree_id=f"ree-{allocation_id}",
        location_id="lab-1",
        image=image,
    )
    return isolation.ensure(allocation, "wb-1", "token")


def _only_status(frames: list[Frame]) -> AllocationStatusFrame:
    statuses = [frame for frame in frames if isinstance(frame, AllocationStatusFrame)]
    assert len(statuses) == 1
    return statuses[0]


def _only_run_call(calls: list[tuple[str, ...]]) -> tuple[str, ...]:
    run_calls = [call for call in calls if call[:1] == ("create",) and "--init" in call]
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
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))

    def fake_docker_out(*args: str, timeout: int = 60) -> str:
        docker_calls.append(args)
        return "scratch-cid"

    monkeypatch.setattr(lc_mod, "run_docker_out", fake_docker_out)
    monkeypatch.setattr(lc_mod, "run_docker_silent", lambda *args: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))
    monkeypatch.setattr(lc_mod, "_image_has_nix", lambda image: image_has_nix)
    monkeypatch.setattr(lc_mod, "_container_path_exists", lambda cid, path: volume_populated)
    return docker_calls


def test_provision_injects_bundle_into_foreign_image(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str, tools_bundle_dir: str
) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=False)

    isolation = DockerIsolation(exec_bundle_dir=exec_bundle_dir, tools_bundle_dir=tools_bundle_dir)
    frames = list(_provision(isolation, "ree1", _spec("docker:dind")))

    assert _only_status(frames).allocation_id == "ree1"
    assert any(
        "REPO2REE_EXEC_PATH=/nix/store/aaa-exec/bin/repo2ree-exec" in part for call in docker_calls for part in call
    )

    run_call = _only_run_call(docker_calls)
    # The store volume is mounted read-only at /nix/store and the bench is kept
    # alive by the bundle's static pause binary, not the image's sleep.
    assert isolation._bundle is not None
    volume = isolation._bundle.volume_name
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

    isolation = DockerIsolation(exec_bundle_dir=exec_bundle_dir)
    frames = list(_provision(isolation, "ree1", _spec("repo2ree-workbench:edge")))

    # Legacy path: PATH executor, plain sleep, no store mount.
    assert _only_status(frames).allocation_id == "ree1"
    run_call = _only_run_call(docker_calls)
    assert run_call[-1] == "repo2ree-workbench:edge"
    assert not any("/nix/store" in part for part in run_call)
    assert any(isinstance(f, LogFrame) and "skipping executor injection" in f.message for f in frames)


def test_populate_skipped_when_volume_already_populated(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)

    isolation = DockerIsolation(exec_bundle_dir=exec_bundle_dir)
    list(_provision(isolation, "ree1", _spec("docker:dind")))
    # The sentinel was found; no closure paths were copied.
    assert not any(call[0] == "cp" and call[1].startswith("/nix/store/") for call in docker_calls)

    # A second provision short-circuits before even touching docker for the volume.
    docker_calls.clear()
    list(_provision(isolation, "ree2", _spec("docker:dind")))
    assert not any(call[:2] == ("volume", "create") and call[2].startswith("repo2ree-store-") for call in docker_calls)


def test_misconfigured_bundle_dir_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        DockerIsolation(exec_bundle_dir=str(tmp_path / "missing-bundle"))


def test_a_default_command_that_exits_is_rescued_by_the_pause_binary(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str
) -> None:
    # alpine's detached /bin/sh reads EOF and exits at once. The image is still a
    # usable bench — nothing about it depends on that shell staying up — so the
    # injected pause binary holds it open rather than the provision failing.
    docker_calls = _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)
    monkeypatch.setattr(
        lc_mod,
        "container_running",
        lambda name: len([call for call in docker_calls if call[:1] == ("create",) and "--init" in call]) >= 2,
    )

    isolation = DockerIsolation(exec_bundle_dir=exec_bundle_dir)
    frames = list(_provision(isolation, "ree1", _spec("alpine")))

    run_calls = [call for call in docker_calls if call[:1] == ("create",) and "--init" in call]
    assert len(run_calls) == 2
    assert run_calls[0][-1] == "alpine"
    # The duration matters: busybox `sleep` with no operand prints usage and
    # exits, which is how this fallback silently failed to keep anything alive.
    assert run_calls[1][-2:] == ("/nix/store/bbb-busybox/bin/sleep", "infinity")
    assert ("rm", "-f", "-v", "repo2ree-wb-ree1") in docker_calls
    assert not any(isinstance(f, ErrorFrame) for f in frames)
    # The restart policy is only applied to the attempt that proved viable.
    assert [call for call in docker_calls if call[0] == "update"] == [
        ("update", "--restart", "unless-stopped", "repo2ree-wb-ree1")
    ]


def test_bench_that_cannot_stay_up_is_an_error_frame(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    _mock_docker_plumbing(monkeypatch, image_has_nix=False, volume_populated=True)
    monkeypatch.setattr(lc_mod, "container_running", lambda name: False)

    frames = list(_provision(DockerIsolation(exec_bundle_dir=exec_bundle_dir), "ree1", _spec("broken:img")))
    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors
    assert "default command and the pause command both exited" in errors[0].detail
    assert not any(isinstance(f, AllocationStatusFrame) for f in frames)


# ================================================
# Bench probe (doctor)
# ================================================


# Bound before the autouse fixture replaces the module attribute, so the
# probe's own tests exercise the real implementation.
_real_probe_bench = lc_mod._probe_bench
_real_resolved_image = lc_mod._resolved_image


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


def test_probe_warns_without_a_reachable_docker_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_is_running_leans_available_on_an_indeterminate_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """A liveness gate that can't reach the daemon must not declare a healthy
    bench dead — doing so fails the session's next action with a spurious
    "workbench unavailable". After a retry, an unresolved probe leans available."""
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    def _unknown(_name: str) -> bool:
        raise ContainerStateUnknownError("daemon blip")

    monkeypatch.setattr(lc_mod, "container_running", _unknown)
    assert DockerIsolation().inspect("probe") is True


def test_is_running_reports_a_confirmed_stopped_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    """A confirmed-down verdict is passed through unchanged — leaning available
    is only for the indeterminate case, never for a bench that is really gone."""
    monkeypatch.setattr(lc_mod, "container_running", lambda _name: False)
    assert DockerIsolation().inspect("probe") is False


def test_probe_helpers_record_failure_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: these helpers hard-coded "succeeded" in a finally, so a probe
    that timed out was logged as a phantom success. Routed through docker_op,
    the timeout is now recorded as a failure."""
    from repo2ree_docker import ops as ops_mod

    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ops_mod,
        "record_docker_operation",
        lambda operation, _started_at, status: recorded.append((operation, status)),
    )

    def _timeout(*_a: object, **_k: object) -> _FakeCompleted:
        raise subprocess.TimeoutExpired(cmd="docker", timeout=30)

    monkeypatch.setattr(subprocess, "run", _timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        lc_mod._image_present("img")
    assert recorded[-1] == ("docker.image_inspect", "failed")

    with pytest.raises(subprocess.TimeoutExpired):
        lc_mod._container_path_exists("cid", "/x")
    assert recorded[-1] == ("docker.cp_probe_path", "failed")


# ================================================
# Benches whose default command exits immediately
# ================================================


def _run_calls(calls: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return [call for call in calls if call[:1] == ("create",) and "--init" in call]


def _exits_immediately(monkeypatch: pytest.MonkeyPatch, *, viable_after: int) -> list[tuple[str, ...]]:
    """Report the bench as dead until the ``viable_after``-th start attempt."""
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "run_docker_silent", lambda *args: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "run_docker_out", lambda *args, timeout=60: "scratch-cid")
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))
    monkeypatch.setattr(lc_mod, "_image_has_nix", lambda image: False)
    monkeypatch.setattr(lc_mod, "_container_path_exists", lambda cid, path: True)
    monkeypatch.setattr(
        lc_mod,
        "container_running",
        lambda name: len(_run_calls(docker_calls)) >= viable_after,
    )
    return docker_calls


def test_a_dead_default_command_falls_back_to_the_injected_pause_binary(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str
) -> None:
    # A dind image in host-socket mode lands here by construction: its default
    # command is dockerd, which cannot start without --privileged, and
    # host-socket withholds it deliberately. What that mode needs is the
    # mounted host socket, so a paused bench is the correct bench.
    docker_calls = _exits_immediately(monkeypatch, viable_after=2)

    isolation = DockerIsolation(docker_mode="host-socket", exec_bundle_dir=exec_bundle_dir)
    frames = list(_provision(isolation, "ree-dead-cmd", _spec("docker:29-dind")))

    first, second = _run_calls(docker_calls)
    # The first attempt hands the image nothing and lets its own command run.
    assert first[-1] == "docker:29-dind"
    # The retry appends the bundle's static pause binary *and its duration* as
    # the command; busybox `sleep` with no operand exits instead of pausing.
    assert second[-3:] == ("docker:29-dind", "/nix/store/bbb-busybox/bin/sleep", "infinity")
    # The dead attempt is removed so the retry can reuse the container name.
    assert ("rm", "-f", "-v", "repo2ree-wb-ree-dead-cmd") in docker_calls
    # Falling back is reported: in dind mode the same path means the nested
    # daemon died, and a silently daemon-dead bench is the failure this
    # provisioner exists to make falsifiable.
    assert any(isinstance(f, LogFrame) and "holding the bench open with" in f.message for f in frames)
    assert _only_status(frames)


def test_a_dead_default_command_without_a_bundle_uses_the_image_own_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Nothing was injected, so the bench is asked to pause with whatever `sleep`
    # its own PATH provides rather than the provision failing outright.
    docker_calls = _exits_immediately(monkeypatch, viable_after=2)

    isolation = DockerIsolation(docker_mode="host-socket")
    frames = list(_provision(isolation, "ree-no-bundle", _spec("docker:29-dind")))

    assert _run_calls(docker_calls)[1][-2:] == ("sleep", "infinity")
    assert not [f for f in frames if isinstance(f, ErrorFrame)]


def test_a_bench_that_dies_under_the_pause_command_too_fails_provisioning(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str
) -> None:
    # Nothing keeps this image alive; the fallback must not paper over that.
    docker_calls = _exits_immediately(monkeypatch, viable_after=99)

    isolation = DockerIsolation(docker_mode="host-socket", exec_bundle_dir=exec_bundle_dir)

    frames = list(_provision(isolation, "ree-never-up", _spec("broken:latest")))

    errors = [f for f in frames if isinstance(f, ErrorFrame)]
    assert errors
    assert "default command and the pause command both exited" in errors[0].detail
    assert len(_run_calls(docker_calls)) == 2


# ================================================
# The control-plane URL handed to the resident workbench
# ================================================


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        # A provider run from source defaults to loopback, which inside the bench
        # is the bench. This is the case the README's own recipe produces.
        ("ws://localhost:8000/workbench/connect", "ws://host.docker.internal:8000/workbench/connect"),
        ("ws://127.0.0.1:8000/workbench/connect", "ws://host.docker.internal:8000/workbench/connect"),
        ("ws://[::1]:8000/workbench/connect", "ws://host.docker.internal:8000/workbench/connect"),
        # No port, and a scheme that is not ws, still round-trip correctly.
        ("wss://localhost/workbench/connect", "wss://host.docker.internal/workbench/connect"),
        # A real host is the operator's decision and is never second-guessed.
        ("ws://control.example:8000/workbench/connect", "ws://control.example:8000/workbench/connect"),
        ("ws://host.docker.internal:8000/workbench/connect", "ws://host.docker.internal:8000/workbench/connect"),
    ],
)
def test_loopback_control_plane_urls_are_rewritten_for_the_bench(configured: str, expected: str) -> None:
    isolation = DockerIsolation(workbench_api_ws_url=configured)

    assert isolation._workbench_api_ws_url == expected


def test_a_host_networked_bench_keeps_its_loopback_url() -> None:
    # Sharing the host's network namespace is the one case where the bench's
    # loopback already *is* the control plane's.
    isolation = DockerIsolation(
        workbench_api_ws_url="ws://localhost:8000/workbench/connect",
        workbench_network="host",
    )

    assert isolation._workbench_api_ws_url == "ws://localhost:8000/workbench/connect"


def test_the_rewritten_url_is_what_the_resident_workbench_receives(monkeypatch: pytest.MonkeyPatch) -> None:
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    isolation = DockerIsolation(workbench_api_ws_url="ws://localhost:8000/workbench/connect")
    list(_provision(isolation, "ree-url", _spec("repo2ree-workbench:test")))

    exec_call = next(call for call in docker_calls if call[:2] == ("exec", "-d"))
    assert _has_option_value(exec_call, "-e", "WORKBENCH_API_WS_URL=ws://host.docker.internal:8000/workbench/connect")
    # The bench is given the name that URL depends on.
    run_call = _only_run_call(docker_calls)
    assert _has_option_value(run_call, "--add-host", "host.docker.internal:host-gateway")


# ------------------------------------------------
# What the bench actually came up on
# ------------------------------------------------


def test_a_registry_image_resolves_to_its_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = "docker.io/library/docker@sha256:" + "a" * 64
    monkeypatch.setattr(lc_mod, "run_docker_out", lambda *args, timeout=60: pinned)

    assert _real_resolved_image("docker:29-dind") == pinned


def test_an_image_with_no_digest_resolves_to_the_ref_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    # A locally built image has no RepoDigests, so the format yields "". The
    # record must say what was asked for rather than claim an empty pin.
    monkeypatch.setattr(lc_mod, "run_docker_out", lambda *args, timeout=60: "")

    assert _real_resolved_image("repo2ree-workbench:local") == "repo2ree-workbench:local"


def test_an_unreadable_digest_does_not_fail_a_provision_that_worked(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: str, timeout: int = 60) -> str:
        raise RuntimeError("docker inspect failed")

    monkeypatch.setattr(lc_mod, "run_docker_out", explode)

    assert _real_resolved_image("docker:29-dind") == "docker:29-dind"


def test_the_terminal_status_frame_reports_the_resolved_image(monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = "docker.io/library/docker@sha256:" + "b" * 64
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: None)
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: True)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))
    monkeypatch.setattr(lc_mod, "_resolved_image", lambda image: pinned)

    frames = list(_provision(DockerIsolation(), "ree-pinned", _spec("docker:29-dind")))

    assert _only_status(frames).resolved_image == pinned


def test_a_reconnected_allocation_still_reports_its_image(monkeypatch: pytest.MonkeyPatch) -> None:
    # The early return for an allocation whose bench already exists is the other
    # way out of ensure(); a frame missing the field there would blank a record
    # that had one.
    monkeypatch.setattr(lc_mod, "_allocation_image", lambda name: "docker:29-dind")
    monkeypatch.setattr(lc_mod, "container_running", lambda name: True)
    monkeypatch.setattr(lc_mod, "_resolved_image", lambda image: f"pinned::{image}")

    frames = list(_provision(DockerIsolation(), "ree-existing", _spec("docker:29-dind")))

    assert _only_status(frames).resolved_image == "pinned::docker:29-dind"


# ------------------------------------------------
# What the bench is told to do with its own telemetry
# ------------------------------------------------


def _bench_env(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> tuple[str, ...]:
    docker_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: docker_calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    isolation = DockerIsolation(**kwargs)  # type: ignore[arg-type]
    list(_provision(isolation, "ree-telemetry", _spec("repo2ree-workbench:test")))

    return next(call for call in docker_calls if call[:2] == ("exec", "-d"))


def test_a_bench_relays_its_own_spans_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    exec_call = _bench_env(monkeypatch)

    assert _has_option_value(exec_call, "-e", "WORKBENCH_TELEMETRY=relay")
    # Never inherited: this provider's endpoint is reachable from *here*, and a
    # bench on an isolated network that took it would retry an unroutable
    # address. Without one its logs and metrics are no-ops.
    assert not any(value.startswith("OTLP_ENDPOINT=") for value in exec_call)


def test_a_bench_told_to_export_directly_is_given_its_own_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    exec_call = _bench_env(
        monkeypatch,
        workbench_telemetry="direct",
        workbench_otlp_endpoint="http://collector.internal:4318",
    )

    assert _has_option_value(exec_call, "-e", "WORKBENCH_TELEMETRY=direct")
    assert _has_option_value(exec_call, "-e", "OTLP_ENDPOINT=http://collector.internal:4318")


def test_telemetry_can_be_turned_off_for_every_bench_this_provider_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    # The off switch lives here because an operator configures the provider,
    # never the bench containers it starts.
    exec_call = _bench_env(monkeypatch, workbench_telemetry="off")

    assert _has_option_value(exec_call, "-e", "WORKBENCH_TELEMETRY=off")
    assert not any(value.startswith("OTLP_ENDPOINT=") for value in exec_call)


class _FakeDaemon:
    """Containers, volumes, and what was copied into them: enough of a daemon to hold the populate lock."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.containers: dict[str, dict[str, str]] = {}
        self.mounts: dict[str, str] = {}
        self.volumes: dict[str, set[str]] = {}
        self.calls: list[tuple[str, ...]] = []
        self.fail_copy = False
        monkeypatch.setattr(lc_mod, "run_docker", self.run)
        monkeypatch.setattr(lc_mod, "run_docker_out", self.out)
        monkeypatch.setattr(lc_mod, "run_docker_remove", self.remove)
        monkeypatch.setattr(lc_mod, "run_docker_silent", self.silent)
        monkeypatch.setattr(
            lc_mod,
            "_container_path_exists",
            lambda cid, path: path.rsplit("/", 1)[-1] in self.volumes[self.mounts[cid]],
        )

    def run(self, *args: str, timeout: int = 60) -> None:
        self.calls.append(args)
        if args[:2] == ("volume", "create"):
            self.volumes.setdefault(args[2], set())
        elif args[0] == "cp":
            if self.fail_copy:
                raise RuntimeError("docker cp failed: disk full")
            cid, _, target = args[2].partition(":")
            self.volumes[self.mounts[cid]].add(target.rsplit("/", 1)[-1] if target != "/bundle-store" else args[1])

    def out(self, *args: str, timeout: int = 60) -> str:
        self.calls.append(args)
        if args[0] == "inspect":
            return self.containers[args[-1]][lc_mod._LOCKED_AT_LABEL]
        assert args[0] == "create"
        name = args[args.index("--name") + 1] if "--name" in args else f"scratch-{len(self.calls)}"
        if name in self.containers:
            raise RuntimeError(f'docker create failed: Conflict. The container name "/{name}" is already in use')
        key, _, value = args[args.index("--label") + 1].partition("=") if "--label" in args else ("", "", "")
        self.containers[name] = {key: value} if key else {}
        if "-v" in args:
            self.mounts[name] = args[args.index("-v") + 1].split(":", 1)[0]
        return name

    def remove(self, *args: str) -> None:
        self.calls.append(args)
        if args[:2] == ("volume", "rm"):
            self.volumes.pop(args[2], None)

    def silent(self, *args: str) -> None:
        self.calls.append(args)
        if args[:2] == ("rm", "-f"):
            self.containers.pop(args[-1], None)

    def copied(self) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[0] == "cp" and call[1].startswith("/nix/store/")]


_BUNDLE = InjectionBundle(
    exec_path="/nix/store/aaa-exec/bin/repo2ree-exec",
    workbench_path=None,
    pause_path="/nix/store/bbb-busybox/bin/sleep",
    store_sources=("/nix/store/aaa-exec", "/nix/store/bbb-busybox"),
    volume_name="repo2ree-store-abc",
    tool_env={},
)
_LOCK = f"{lc_mod._POPULATE_LOCK_PREFIX}{_BUNDLE.volume_name}"


def _populate(exec_bundle_dir: str) -> list[Any]:
    return list(DockerIsolation(exec_bundle_dir=exec_bundle_dir)._ensure_store_volume("docker:dind", _BUNDLE))


def test_a_volume_another_provider_is_populating_is_waited_for(
    monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str
) -> None:
    """Providers sharing a daemon share the volume; only one of them copies into it."""
    daemon = _FakeDaemon(monkeypatch)
    daemon.containers[_LOCK] = {lc_mod._LOCKED_AT_LABEL: f"{time.time():.0f}"}

    def other_provider_finishes(_seconds: float) -> None:
        daemon.volumes[_BUNDLE.volume_name] = {"aaa-exec", lc_mod._POPULATED_SENTINEL}
        daemon.containers.pop(_LOCK)

    monkeypatch.setattr(time, "sleep", other_provider_finishes)
    frames = _populate(exec_bundle_dir)

    assert any(isinstance(frame, LogFrame) and "waiting for another provider" in frame.message for frame in frames)
    assert daemon.copied() == []
    assert _LOCK not in daemon.containers


def test_a_half_populated_volume_is_rebuilt_from_empty(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    """A provider that died mid-copy left symlinks a second copy would collide with."""
    daemon = _FakeDaemon(monkeypatch)
    daemon.volumes[_BUNDLE.volume_name] = {"/nix/store/aaa-exec"}

    _populate(exec_bundle_dir)

    removed = daemon.calls.index(("volume", "rm", _BUNDLE.volume_name))
    assert removed < daemon.calls.index(daemon.copied()[0])
    assert lc_mod._POPULATED_SENTINEL in daemon.volumes[_BUNDLE.volume_name]
    assert _LOCK not in daemon.containers


def test_a_lock_its_holder_abandoned_is_broken(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    daemon = _FakeDaemon(monkeypatch)
    abandoned = time.time() - lc_mod._POPULATE_LOCK_STALE_SECONDS - 60
    daemon.containers[_LOCK] = {lc_mod._LOCKED_AT_LABEL: f"{abandoned:.0f}"}
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    _populate(exec_bundle_dir)

    assert len(daemon.copied()) == len(_BUNDLE.store_sources)
    assert _LOCK not in daemon.containers


def test_the_lock_is_released_when_a_copy_fails(monkeypatch: pytest.MonkeyPatch, exec_bundle_dir: str) -> None:
    daemon = _FakeDaemon(monkeypatch)
    daemon.fail_copy = True

    with pytest.raises(RuntimeError, match="disk full"):
        _populate(exec_bundle_dir)

    assert _LOCK not in daemon.containers
    assert lc_mod._POPULATED_SENTINEL not in daemon.volumes[_BUNDLE.volume_name]


# ================================================
# Bench DNS and the bench's own log
# ================================================


def _dns_plumbing(monkeypatch: pytest.MonkeyPatch, discovered: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Docker calls in order, with the daemon.json write and each discovery recorded among them."""
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker", lambda *args, timeout=60: calls.append(args))
    monkeypatch.setattr(lc_mod, "_image_present", lambda image: False)
    monkeypatch.setattr(lc_mod, "_docker_stream_lines", lambda *args, timeout=600: iter(()))

    def discover(image: str) -> tuple[str, ...]:
        calls.append(("discover", image))
        return discovered

    monkeypatch.setattr(lc_mod, "discover", discover)
    monkeypatch.setattr(
        lc_mod,
        "write_daemon_settings",
        lambda container, settings: calls.append(("daemon.json", container, *settings.get("dns", []))),
    )
    return calls


def _log_messages(frames: list[Frame]) -> list[str]:
    return [frame.message for frame in frames if isinstance(frame, LogFrame)]


def test_discovered_resolvers_are_in_the_bench_daemon_json_before_the_bench_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _dns_plumbing(monkeypatch, discovered=("10.168.68.254",))

    frames = list(_provision(DockerIsolation(), "ree1", "docker:dind"))

    steps = [call[0] for call in calls if call[0] in {"create", "daemon.json", "start"}]
    assert steps == ["create", "daemon.json", "start"]
    assert ("daemon.json", "repo2ree-wb-ree1", "10.168.68.254") in calls
    assert "bench dns: 10.168.68.254 (auto)" in _log_messages(frames)


def test_discovery_runs_once_per_provider_not_once_per_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _dns_plumbing(monkeypatch, discovered=("10.0.0.53",))
    isolation = DockerIsolation()

    list(_provision(isolation, "ree1", "docker:dind"))
    list(_provision(isolation, "ree2", "docker:dind"))

    assert [call for call in calls if call[0] == "discover"] == [("discover", "docker:dind")]
    assert ("daemon.json", "repo2ree-wb-ree2", "10.0.0.53") in calls


def test_configured_resolvers_are_used_without_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _dns_plumbing(monkeypatch, discovered=("10.0.0.53",))

    frames = list(_provision(DockerIsolation(workbench_dns="192.0.2.1, 192.0.2.2"), "ree1", "docker:dind"))

    assert not [call for call in calls if call[0] == "discover"]
    assert ("daemon.json", "repo2ree-wb-ree1", "192.0.2.1", "192.0.2.2") in calls
    assert "bench dns: 192.0.2.1, 192.0.2.2 (PROVIDER_WORKBENCH_DNS)" in _log_messages(frames)


@pytest.mark.parametrize(
    ("isolation_args"), [{"workbench_dns": "off"}, {"docker_mode": "host-socket"}], ids=["off", "host-socket"]
)
def test_bench_daemons_are_left_alone_when_off_or_without_one(
    monkeypatch: pytest.MonkeyPatch, isolation_args: dict[str, str]
) -> None:
    calls = _dns_plumbing(monkeypatch, discovered=("10.0.0.53",))

    list(_provision(DockerIsolation(**isolation_args), "ree1", "docker:dind"))

    assert not [call for call in calls if call[0] in {"discover", "daemon.json"}]


def test_finding_only_docker_fallback_warns_on_every_bench_and_starts_it_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _dns_plumbing(monkeypatch, discovered=())
    isolation = DockerIsolation()

    first = list(_provision(isolation, "ree1", "docker:dind"))
    second = list(_provision(isolation, "ree2", "docker:dind"))

    assert not [call for call in calls if call[0] == "daemon.json"]
    assert len([call for call in calls if call[0] == "discover"]) == 1
    for frames in (first, second):
        warnings = [frame.message for frame in frames if isinstance(frame, LogFrame) and frame.level == "warn"]
        assert any("PROVIDER_WORKBENCH_DNS" in message for message in warnings)
    assert _only_status(first).allocation_id == "ree1"


def test_a_failed_discovery_is_retried_on_the_next_bench(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _dns_plumbing(monkeypatch)
    attempts = iter([None, ("10.0.0.53",)])

    def discover(image: str) -> tuple[str, ...]:
        calls.append(("discover", image))
        found = next(attempts)
        if found is None:
            raise RuntimeError("no cat in this image")
        return found

    monkeypatch.setattr(lc_mod, "discover", discover)
    isolation = DockerIsolation()

    first = list(_provision(isolation, "ree1", "distroless"))
    list(_provision(isolation, "ree2", "docker:dind"))

    assert _only_status(first).allocation_id == "ree1"
    assert [call[1] for call in calls if call[0] == "discover"] == ["distroless", "docker:dind"]
    assert ("daemon.json", "repo2ree-wb-ree2", "10.0.0.53") in calls


def test_a_registry_mirror_reaches_every_dind_bench_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns_plumbing(monkeypatch)
    written: list[dict[str, object]] = []
    monkeypatch.setattr(lc_mod, "write_daemon_settings", lambda container, settings: written.append(settings))

    frames = list(
        _provision(
            DockerIsolation(workbench_dns="off", workbench_registry_mirror="http://mirror:5000"), "ree1", "docker:dind"
        )
    )

    assert written == [{"registry-mirrors": ["http://mirror:5000"], "insecure-registries": ["mirror:5000"]}]
    assert "bench registry mirror: http://mirror:5000" in _log_messages(frames)


def test_a_failed_provision_shows_the_bench_s_own_log(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns_plumbing(monkeypatch)
    monkeypatch.setattr(lc_mod, "_bench_log_tail", lambda container, lines: "dockerd: failed to mount overlay")
    monkeypatch.setattr(lc_mod, "container_running", lambda name: False)

    frames = list(_provision(DockerIsolation(), "ree1", "docker:dind"))

    assert "bench log: dockerd: failed to mount overlay" in _log_messages(frames)
    assert any(isinstance(frame, ErrorFrame) for frame in frames)


def test_release_keeps_the_bench_s_own_log_in_the_provider_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    removed: list[tuple[str, ...]] = []
    monkeypatch.setattr(lc_mod, "run_docker_remove", lambda *args: removed.append(args))
    monkeypatch.setattr(
        lc_mod,
        "_bench_log_tail",
        lambda container, lines: 'msg="No non-localhost DNS nameservers are left in resolv.conf"',
    )

    with caplog.at_level("INFO", logger=lc_mod.__name__):
        DockerIsolation().release("ree1")

    assert "No non-localhost DNS nameservers" in caplog.text
    assert removed[0] == ("rm", "-f", "-v", "repo2ree-wb-ree1")
