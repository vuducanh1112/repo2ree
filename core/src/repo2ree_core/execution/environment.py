"""What a step's scripts run in, as the receipts that step writes record it.

The workbench says where it runs scripts (``REPO2REE_ENVIRONMENT``, JSON: the backend, and the
image digest, host, and script engine it knows of). Without it the executor describes the host it
is on itself, so a step never records nothing.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from pydantic import ValidationError

from repo2ree_ree.environment import EnvironmentDefinition, EnvironmentObservation, HostFingerprint

ENVIRONMENT_VARIABLE = "REPO2REE_ENVIRONMENT"
_OS_RELEASE = Path("/etc/os-release")


def observe_environment(declared: EnvironmentDefinition | None) -> EnvironmentObservation:
    """The environment a step runs in under ``declared``: as the workbench states it, or this host."""
    stated = os.environ.get(ENVIRONMENT_VARIABLE, "").strip()
    if stated:
        try:
            return EnvironmentObservation.model_validate({**json.loads(stated), "declared": declared})
        except (ValueError, ValidationError):
            pass  # A statement this executor cannot read is no statement: describe the host instead.
    return EnvironmentObservation(declared=declared, backend="host", host=host_fingerprint())


def host_fingerprint(container_engine: str = "") -> HostFingerprint:
    return HostFingerprint(
        os=_os_name(),
        arch=platform.machine() or "unknown",
        kernel=platform.release(),
        container_engine=container_engine,
    )


def _os_name() -> str:
    try:
        for line in _OS_RELEASE.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.partition("=")[2].strip().strip('"') or platform.system()
    except OSError:
        pass
    return platform.system() or "unknown"
