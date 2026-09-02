"""Observe execution capabilities from inside the supplied workbench."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from repo2ree_protocol.workbench import WorkbenchCapabilities


def observe_capabilities(root: Path, exec_path: str, substrate_hint: str = "") -> WorkbenchCapabilities:
    root_writable = _root_writable(root)
    executor_available = bool(shutil.which(exec_path) or Path(exec_path).is_file())
    docker_version = ""
    docker_mode: Literal["nested", "host-socket", "unknown"] | None = None
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            docker_version = result.stdout.strip()
            if substrate_hint == "docker-nested":
                docker_mode = "nested"
            elif substrate_hint == "docker-host-socket":
                docker_mode = "host-socket"
            else:
                docker_mode = "unknown"
    return WorkbenchCapabilities(
        root_writable=root_writable,
        executor_available=executor_available,
        docker_mode=docker_mode,
        docker_version=docker_version,
    )


def _root_writable(root: Path) -> bool:
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root):
            return True
    except OSError:
        return False
