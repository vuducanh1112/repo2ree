from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from repo2ree_protocol.machine import MachineFacts
from repo2ree_ree.working_environment import HostFingerprint, WorkingEnvironmentObservation

_OS_RELEASE = Path("/etc/os-release")


@dataclass(frozen=True)
class ProbeResult:
    returncode: int | None
    stdout: str
    stderr: str


def observe_working_environment() -> WorkingEnvironmentObservation:
    return WorkingEnvironmentObservation(host=host_fingerprint(), container=in_container())


def machine_facts() -> MachineFacts:
    return MachineFacts(arch=platform.machine(), gpus=_gpu_count(), container=in_container())


def host_fingerprint() -> HostFingerprint:
    return HostFingerprint(os=_os_name(), arch=platform.machine() or "unknown", kernel=platform.release())


def in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def probe(workspace: Path, argv: list[str], *, seconds: float) -> ProbeResult:
    try:
        done = subprocess.run(argv, cwd=workspace, check=False, capture_output=True, text=True, timeout=seconds)
    except subprocess.TimeoutExpired as expired:
        return ProbeResult(None, _text(expired.stdout), _text(expired.stderr))
    return ProbeResult(done.returncode, done.stdout, done.stderr)


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
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        listed = subprocess.run(["nvidia-smi", "-L"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in listed.stdout.splitlines() if line.startswith("GPU ")) if listed.returncode == 0 else 0
