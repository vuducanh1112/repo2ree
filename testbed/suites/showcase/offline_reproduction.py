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
    machine = f"ree-offline-{os.getpid()}-{time.monotonic_ns()}"
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
