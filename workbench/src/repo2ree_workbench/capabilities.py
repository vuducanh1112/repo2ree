"""What this workbench offers the scripts it runs, as its hello reports it."""

from __future__ import annotations

import platform
import shutil
import subprocess

from repo2ree_protocol.workbench import WorkbenchCapabilities

_ENGINES = ("docker", "podman")


def detect_capabilities() -> WorkbenchCapabilities:
    """This host's architecture, container engine, and GPUs, for scripts run on the host itself.

    A script run on the host reaches the host's engine directly, so an installed engine is one
    its scripts can use.
    """
    engine = any(shutil.which(name) for name in _ENGINES)
    return WorkbenchCapabilities(
        arch=platform.machine(),
        container_engine=engine,
        script_engine="socket" if engine else "none",
        gpus=_gpu_count(),
    )


def _gpu_count() -> int:
    """NVIDIA GPUs, as ``nvidia-smi -L`` lists them; none where it is absent or does not answer."""
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        listed = subprocess.run(["nvidia-smi", "-L"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in listed.stdout.splitlines() if line.startswith("GPU ")) if listed.returncode == 0 else 0
