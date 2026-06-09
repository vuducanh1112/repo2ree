"""Renovate adapter.

Parses ``renovate --platform=local --dry-run=extract`` stdout and produces a
``DependencyInventory``.  All Renovate-specific knowledge — CLI flags, env
vars, payload shapes — is confined to this module.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..dependency_inventory import Dependency, DependencyInventory

# ================================================
# Types
# ================================================

LogFn = Callable[[str, str, str], None]  # (stream, level, message)


# ================================================
# Constants
# ================================================

_RENOVATE_EXTRACT_MARKER = "Extracted dependencies (repository=local)"
_DOCKER_DATASOURCE = "docker"


# ================================================
# Entry point
# ================================================


def run_extract(workspace_path: Path, log: LogFn) -> DependencyInventory | None:
    """Run ``renovate --dry-run=extract`` and return the inventory.

    All stdout/stderr lines are forwarded to ``log``.  Returns ``None`` when
    Renovate produced no parseable dependency output.
    """
    if not workspace_path.is_dir():
        raise ValueError(f"workspace_path must be an existing directory: {workspace_path}")

    command = ["renovate", "--platform=local", "--dry-run=extract"]
    log("system", "info", "$ " + " ".join(shlex.quote(c) for c in command))

    env = os.environ.copy()
    env["LOG_LEVEL"] = "info"
    completed = subprocess.run(
        command,
        cwd=str(workspace_path),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    for line in (completed.stdout or "").splitlines():
        if line.strip():
            log("stdout", "info", line)
    for line in (completed.stderr or "").splitlines():
        if line.strip():
            log("stderr", "warn", line)

    if completed.returncode != 0:
        log("system", "error", f"Tool exited with code {completed.returncode}")

    return parse_renovate_stdout(completed.stdout)


# ================================================
# Helpers
# ================================================


def parse_renovate_stdout(stdout: str) -> DependencyInventory | None:
    """Return a ``DependencyInventory`` from Renovate ``--dry-run=extract`` stdout.

    Returns ``None`` when the output cannot be parsed (marker absent or invalid
    JSON), which the caller can treat as a tool failure.
    """
    payload = _extract_json_payload(stdout)
    if payload is None:
        return None
    return _inventory_from_payload(payload)


def _extract_json_payload(stdout: str) -> dict[str, Any] | None:
    marker_pos = stdout.find(_RENOVATE_EXTRACT_MARKER)
    if marker_pos < 0:
        return None
    json_start = stdout.find("{", marker_pos)
    if json_start < 0:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(stdout[json_start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _package_files(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("packageFiles")
    package_files = inner if isinstance(inner, dict) else payload
    return {k: v for k, v in package_files.items() if isinstance(v, list)}


def _is_container_dep(manager: str, dep: dict[str, Any]) -> bool:
    return dep.get("datasource") == _DOCKER_DATASOURCE or manager.startswith(("dockerfile", "docker-compose"))


def _inventory_from_payload(payload: dict[str, Any]) -> DependencyInventory:
    package_files = _package_files(payload)
    deps: list[Dependency] = []
    for manager, files in package_files.items():
        for package_file in files:
            if not isinstance(package_file, dict):
                continue
            manifest_path: str | None = package_file.get("packageFile")
            for dep in package_file.get("deps") or []:
                if not isinstance(dep, dict):
                    continue
                is_container = _is_container_dep(manager, dep)
                name = str(dep.get("depName") or dep.get("packageName") or "?")
                declared = dep.get("currentValue") or None
                locked = dep.get("lockedVersion") or None
                digest = dep.get("currentDigest") or None
                deps.append(
                    Dependency(
                        name=name,
                        declared_version=declared,
                        locked_version=locked,
                        kind="container_image" if is_container else "library",
                        digest=digest,
                        manifest_path=None if is_container else manifest_path,
                    )
                )

    inventory = DependencyInventory(dependencies=deps)

    if not all(d.manifest_path is None for d in inventory.dependencies if d.kind == "container_image"):
        raise AssertionError("container_image deps must not carry a manifest_path")

    return inventory
