"""The bench capability probe behind ``repo2ree-exec doctor``.

Runs inside a freshly provisioned bench and reports, as one JSON document,
whether this environment can actually serve as a workbench: the hard
requirement (a writable ``/ree`` tree) and the soft capabilities (a reachable
docker substrate, which handler tools are present). The agent runs it right
after the bench starts and fails provisioning on ``ok: false`` — a custom env
image that violates the bench contract dies with a specific message here
instead of hanging on its first build.

Capability checks never fail the probe: a bench without docker or syft is a
bench that can't build runtimes or generate SBOMs, which is for the control
plane (and the user who picked the image) to judge.
"""

from __future__ import annotations

import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from repo2ree_core.tooling import find_tool

# Tools core handlers and lifecycle scripts shell out to; each is reported as
# its resolved path or null. Extend alongside nix/tools.nix.
_PROBED_TOOLS = ("syft", "git", "curl", "unzip", "tar", "gzip")

# dockerd may still be starting when the probe runs (the agent probes right
# after the container comes up, and dind daemons take a few seconds); poll
# briefly before declaring the substrate unreachable.
_DOCKER_WAIT_SECONDS = 15.0


def run_doctor(ree_path: Path = Path("/ree"), docker_wait_seconds: float = _DOCKER_WAIT_SECONDS) -> dict[str, Any]:
    """Probe this environment; ``ok`` reflects only the hard requirements."""
    ree_writable = _dir_writable(ree_path)
    return {
        "schema_version": 1,
        "ok": ree_writable,
        "ree_writable": ree_writable,
        "docker": _probe_docker(docker_wait_seconds),
        "tools": {name: find_tool(name) for name in _PROBED_TOOLS},
        "python": platform.python_version(),
    }


def _dir_writable(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".repo2ree-doctor-"):
            return True
    except OSError:
        return False


def _probe_docker(wait_seconds: float) -> dict[str, Any]:
    docker = find_tool("docker")
    if docker is None:
        return {"available": False, "detail": "docker CLI not found"}
    deadline = time.monotonic() + wait_seconds
    detail = ""
    while True:
        # A still-starting dockerd can leave `docker info` *blocking* on a
        # half-open socket, not just failing fast. Treat that timeout as one
        # more "not ready yet" tick — never let it escape and crash the probe,
        # which the agent would read as a bench-contract violation and fail
        # provisioning on a substrate that was merely slow to boot.
        try:
            result = subprocess.run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=min(30.0, wait_seconds),
            )
        except subprocess.TimeoutExpired:
            detail = "daemon did not respond in time"
        else:
            if result.returncode == 0:
                return {"available": True, "server_version": result.stdout.strip()}
            combined = result.stderr or result.stdout
            detail = combined.strip().splitlines()[-1] if combined else ""
        if time.monotonic() >= deadline:
            return {"available": False, "detail": f"daemon not reachable: {detail}"}
        time.sleep(1)
