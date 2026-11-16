"""The working environment a step's scripts run in, as the step observes it.

``ree`` runs every script where it itself runs: whoever provides the compute decides what that is, a host with its
toolchain, a container from an image of their choosing, a cluster's node behind the REE's launch. The REE's check
says what its scripts need; each step records where they ran.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from repo2ree_protocol.machine import MachineFacts
from repo2ree_ree.working_environment import HostFingerprint, WorkingEnvironmentObservation

# The image the compute provider runs ree in, as it reports it; ree cannot see an image from inside it.
REPORTED_IMAGE_VARIABLE = "REPO2REE_IMAGE"
_OS_RELEASE = Path("/etc/os-release")


@dataclass(frozen=True)
class ProbeResult:
    """What a probe printed where the REE's scripts run; ``returncode`` None when it ran out of time."""

    returncode: int | None
    stdout: str
    stderr: str


def observe_working_environment() -> WorkingEnvironmentObservation:
    """Where this step's scripts run: this host, whether it is a container, and the image the provider reports."""
    return WorkingEnvironmentObservation(
        host=host_fingerprint(), container=in_container(), reported_image=_reported_image()
    )


def machine_facts() -> MachineFacts:
    """The machine ree runs on, as ``ree machine`` reports it."""
    return MachineFacts(
        arch=platform.machine(), gpus=_gpu_count(), container=in_container(), reported_image=_reported_image()
    )


def host_fingerprint() -> HostFingerprint:
    return HostFingerprint(os=_os_name(), arch=platform.machine() or "unknown", kernel=platform.release())


def in_container() -> bool:
    """Whether this process runs in a container, as Docker and Podman mark one."""
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def probe(workspace: Path, argv: list[str], *, seconds: float) -> ProbeResult:
    """Run ``argv`` where a script runs, from ``workspace``, for at most ``seconds``, keeping what it prints out of
    the step's logs. A probe reads and writes nothing in the workspace."""
    try:
        done = subprocess.run(argv, cwd=workspace, check=False, capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired as expired:
        return ProbeResult(None, _text(expired.stdout), _text(expired.stderr))
    return ProbeResult(done.returncode, done.stdout, done.stderr)


def _reported_image() -> str | None:
    return os.environ.get(REPORTED_IMAGE_VARIABLE, "").strip() or None


def _text(output: str | bytes | None) -> str:
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


def _os_name() -> str:
    try:
        for line in _OS_RELEASE.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.partition("=")[2].strip().strip('"') or platform.system()
    except OSError:
        pass
    return platform.system() or "unknown"


def _gpu_count() -> int:
    """NVIDIA GPUs, as ``nvidia-smi -L`` lists them; none where it is absent or does not answer."""
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        listed = subprocess.run(["nvidia-smi", "-L"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in listed.stdout.splitlines() if line.startswith("GPU ")) if listed.returncode == 0 else 0
