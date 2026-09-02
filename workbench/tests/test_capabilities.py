"""What the workbench reports about the environment it woke up in.

The compatibility gate rejects a bench whose substrate does not match the
selected profile, so a misread here is indistinguishable from a genuinely
unusable bench — and rejects every provisioning attempt against that profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import repo2ree_workbench.capabilities as capabilities
from repo2ree_protocol.substrate import SubstrateKind
from repo2ree_workbench.capabilities import observe_capabilities

_MOUNTINFO_BIND = (
    "23 28 0:21 / /proc rw,nosuid,relatime - proc proc rw\n"
    "31 28 0:25 / /run rw,nosuid,nodev - tmpfs tmpfs rw\n"
    "42 31 259:2 /run/docker.sock {point} rw,relatime - ext4 /dev/nvme0n1p2 rw\n"
)


@pytest.fixture(autouse=True)
def _no_ambient_docker_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCKER_HOST", raising=False)


def _arrange(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    mountinfo: str = "",
    docker_cli: bool = True,
    versions: list[str] | None = None,
    ready_timeout: float = 0,
) -> list[int]:
    """Stub the three things observation reads: PATH, the daemon, the mounts.

    ``ready_timeout`` defaults to 0 so a test that does not care about the boot
    race still probes once and returns immediately instead of spinning out the
    real 20s window.
    """
    mountinfo_file = tmp_path / "mountinfo"
    mountinfo_file.write_text(mountinfo, encoding="utf-8")
    monkeypatch.setattr(capabilities, "_MOUNTINFO_PATH", mountinfo_file)
    monkeypatch.setattr(capabilities, "_DOCKER_POLL_INTERVAL", 0)
    monkeypatch.setattr(capabilities, "_DOCKER_READY_TIMEOUT", ready_timeout)

    def fake_which(name: str) -> str | None:
        if name == "docker":
            return "/usr/bin/docker" if docker_cli else None
        return f"/usr/bin/{name}"

    monkeypatch.setattr("shutil.which", fake_which)

    replies = list(versions if versions is not None else ["29.0.1"])
    attempts = [0]

    def fake_version() -> str:
        attempts[0] += 1
        return replies.pop(0) if replies else ""

    monkeypatch.setattr(capabilities, "_docker_server_version", fake_version)
    return attempts


def test_a_bind_mounted_host_socket_reads_as_the_shared_substrate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _arrange(monkeypatch, tmp_path, mountinfo=_MOUNTINFO_BIND.format(point="/var/run/docker.sock"))

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.DOCKER_HOST_SOCKET
    assert observed.docker_socket_mounted is True
    assert observed.docker_version == "29.0.1"


def test_a_host_socket_is_still_recognised_when_var_run_is_a_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Alpine — which the stock docker images are built on — ships /var/run as a
    # symlink to /run, so the kernel records the *resolved* mount point. Reading
    # only the literal /var/run spelling reported a shared host daemon as a
    # private nested one, and the gate then rejected every such bench.
    root = tmp_path / "fs"
    (root / "run").mkdir(parents=True)
    (root / "run" / "docker.sock").touch()
    (root / "var").mkdir()
    (root / "var" / "run").symlink_to(root / "run")
    _arrange(monkeypatch, tmp_path, mountinfo=_MOUNTINFO_BIND.format(point=f"{root}/run/docker.sock"))
    monkeypatch.setenv("DOCKER_HOST", f"unix://{root}/var/run/docker.sock")

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.DOCKER_HOST_SOCKET


def test_an_unmounted_socket_reads_as_a_private_nested_daemon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _arrange(monkeypatch, tmp_path, mountinfo="31 28 0:25 / /run rw - tmpfs tmpfs rw\n")

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.DOCKER_NESTED
    assert observed.docker_socket_mounted is False


def test_observation_waits_for_a_nested_daemon_that_is_still_booting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The workbench is exec'd into the bench the moment the container starts, so
    # a single probe races dockerd's boot and reports a docker bench as bare.
    attempts = _arrange(monkeypatch, tmp_path, versions=["", "", "29.0.1"], ready_timeout=20)

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.DOCKER_NESTED
    assert observed.docker_version == "29.0.1"
    assert attempts[0] == 3


def test_a_daemon_that_never_arrives_reads_as_bare_rather_than_hanging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _arrange(monkeypatch, tmp_path, versions=[""])

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.BARE
    assert observed.docker_version is None


def test_a_bench_without_a_docker_client_is_bare_and_probes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    attempts = _arrange(monkeypatch, tmp_path, docker_cli=False)

    observed = observe_capabilities(tmp_path / "ree", "repo2ree-exec")

    assert observed.substrate is SubstrateKind.BARE
    assert attempts[0] == 0


def test_mount_points_containing_escapes_are_decoded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _arrange(
        monkeypatch,
        tmp_path,
        mountinfo="42 31 259:2 / /var/run/odd\\040dir/docker.sock rw - ext4 /dev/sda1 rw\n",
    )
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/odd dir/docker.sock")

    assert observe_capabilities(tmp_path / "ree", "repo2ree-exec").docker_socket_mounted is True


def test_the_root_is_reported_writable_only_when_it_actually_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _arrange(monkeypatch, tmp_path)

    assert observe_capabilities(tmp_path / "ree", "repo2ree-exec").root_writable is True
    assert observe_capabilities(Path("/proc/nonexistent/ree"), "repo2ree-exec").root_writable is False
