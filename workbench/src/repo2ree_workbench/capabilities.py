"""Observe execution capabilities from inside the supplied workbench.

These facts are measured, never taken on trust. The provider does tell the
bench what it built (``WORKBENCH_DOCKER_MODE``), but believing that env var
would make the compatibility gate a tautology: a provider that mis-declares its
own substrate would be waved through. So the substrate is derived from what is
actually reachable from in here.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from repo2ree_protocol.substrate import FixedResources, ObservedCapabilities, SubstrateKind

_DEFAULT_DOCKER_SOCKET = "/var/run/docker.sock"
_MOUNTINFO_PATH = Path("/proc/self/mountinfo")

# A nested daemon is still booting when the workbench is exec'd into a fresh
# bench, so a single probe would read "no docker" off a bench that has it. The
# provider's own doctor probe tolerates ~15s for the same reason; observation
# has to be at least as patient or the two disagree about the same bench.
_DOCKER_READY_TIMEOUT = 20.0
_DOCKER_POLL_INTERVAL = 0.5


def observe_capabilities(root: Path, exec_path: str) -> ObservedCapabilities:
    root_writable = _root_writable(root)
    executor_available = bool(shutil.which(exec_path) or Path(exec_path).is_file())
    docker_version = _await_docker_version()
    docker_socket_mounted = _docker_socket_is_mounted()
    if docker_version is None:
        substrate = SubstrateKind.BARE
    elif docker_socket_mounted:
        substrate = SubstrateKind.DOCKER_HOST_SOCKET
    else:
        substrate = SubstrateKind.DOCKER_NESTED
    return ObservedCapabilities(
        root_writable=root_writable,
        executor_available=executor_available,
        substrate=substrate,
        docker_version=docker_version,
        docker_socket_mounted=docker_socket_mounted,
        resources=_observe_resources(),
    )


def _root_writable(root: Path) -> bool:
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root):
            return True
    except OSError:
        return False


def _docker_socket_path() -> str:
    """The socket this bench's docker client will actually talk to."""
    host = os.environ.get("DOCKER_HOST", "")
    if host.startswith("unix://"):
        return host[len("unix://") :] or _DEFAULT_DOCKER_SOCKET
    return _DEFAULT_DOCKER_SOCKET


def _await_docker_version() -> str | None:
    if not shutil.which("docker"):
        return None
    deadline = time.monotonic() + _DOCKER_READY_TIMEOUT
    while True:
        version = _docker_server_version()
        if version:
            return version
        if time.monotonic() >= deadline:
            return None
        time.sleep(_DOCKER_POLL_INTERVAL)


def _docker_server_version() -> str:
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _unescape_mount_field(field: str) -> str:
    # mountinfo octal-escapes the characters that would otherwise break its own
    # field separators.
    for escape, char in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        field = field.replace(escape, char)
    return field


def _mount_points() -> set[str]:
    try:
        mountinfo = _MOUNTINFO_PATH.read_text(encoding="utf-8")
    except OSError:
        return set()
    points: set[str] = set()
    for line in mountinfo.splitlines():
        fields = line.split(" - ", 1)[0].split()
        if len(fields) > 4:
            points.add(_unescape_mount_field(fields[4]))
    return points


def _docker_socket_is_mounted() -> bool:
    """True when the reachable daemon's socket came from outside this container.

    The mount point the kernel records is the *resolved* destination: the daemon
    follows symlinks in the container path before mounting, and Alpine — which
    the stock docker images are built on — ships ``/var/run`` as a symlink to
    ``/run``. Comparing against one hardcoded spelling therefore reports a
    bind-mounted host socket as a private nested daemon.
    """
    socket_path = Path(_docker_socket_path())
    candidates = {str(socket_path)}
    with contextlib.suppress(OSError):
        candidates.add(str(socket_path.resolve()))
    with contextlib.suppress(OSError):
        # The socket itself is gone when the daemon is down, but its directory
        # still resolves — and the directory is the half that is a symlink.
        candidates.add(str(socket_path.parent.resolve() / socket_path.name))
    return bool(candidates & _mount_points())


def _observe_resources() -> FixedResources:
    cpu_count = _cgroup_cpu_count()
    memory_bytes = _cgroup_memory_bytes()
    return FixedResources(
        cpu_count=cpu_count if cpu_count is not None else float(os.cpu_count() or 1),
        memory_bytes=memory_bytes,
    )


def _cgroup_cpu_count() -> float | None:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="utf-8").split()
        if quota != "max" and int(period) > 0:
            return int(quota) / int(period)
    except (OSError, ValueError):
        pass
    return None


def _cgroup_memory_bytes() -> int | None:
    try:
        value = Path("/sys/fs/cgroup/memory.max").read_text(encoding="utf-8").strip()
        return None if value == "max" else int(value)
    except (OSError, ValueError):
        return None
