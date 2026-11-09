"""A machine of the reviewer's: Docker and a POSIX shell, no repo2ree, and no network."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from repo2ree_testbed.stack.store_images import DOCKER_IMAGE

DAEMON_START_SECONDS = 60
REPRODUCTION_TIMEOUT_SECONDS = 600


def _docker(*args: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)


def reproduce_offline(archive: Path) -> str:
    """Unpack the archive and run ``sh run.sh all`` there, as REPRODUCING.md tells a reviewer: what it printed."""
    machine = f"ree-offline-{os.getpid()}-{time.monotonic_ns()}"
    # An empty TLS directory has the daemon listen on its socket alone: no certificates to make.
    started = _docker(
        *("run", "-d", "--privileged", "--network", "none", "--name", machine),
        *("-e", "DOCKER_TLS_CERTDIR=", DOCKER_IMAGE),
    )
    assert started.returncode == 0, started.stderr
    try:
        deadline = time.monotonic() + DAEMON_START_SECONDS
        while _docker("exec", machine, "docker", "info").returncode != 0:
            assert time.monotonic() < deadline, "the offline machine's Docker never started"
            time.sleep(1)
        # Not /tmp: a tmpfs mounted inside the container, which `docker cp` writes beneath, unseen.
        copied = _docker("cp", str(archive), f"{machine}:/root/ree.zip", timeout=REPRODUCTION_TIMEOUT_SECONDS)
        assert copied.returncode == 0, copied.stderr
        run = _docker(
            *("exec", machine, "sh", "-c", "cd /root && unzip -q ree.zip && cd ree && sh run.sh all"),
            timeout=REPRODUCTION_TIMEOUT_SECONDS,
        )
        output = run.stdout + run.stderr
        assert run.returncode == 0, f"run.sh all failed offline:\n{output[-4000:]}"
        return output
    finally:
        _docker("rm", "-f", "-v", machine)
