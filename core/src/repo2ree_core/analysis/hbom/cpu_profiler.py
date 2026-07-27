from __future__ import annotations

import math
import os
import platform
from pathlib import Path
from typing import Any

from repo2ree_core.domain.hbom import CPUDefinition


def _parse_cpuinfo(cpuinfo_path: Path = Path("/proc/cpuinfo")) -> dict[str, Any]:
    if not cpuinfo_path.exists():
        return {}
    return _parse_cpuinfo_text(cpuinfo_path.read_text(encoding="utf-8"))


def _parse_cpuinfo_text(text: str) -> dict[str, Any]:
    processors: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                processors.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = value.strip()
    if current:
        processors.append(current)

    if not processors:
        return {}

    first = processors[0]
    socket_ids = {entry.get("physical id", "").strip() for entry in processors if entry.get("physical id", "").strip()}
    socket_count = len(socket_ids) or 1

    cores_per_socket = 1
    try:
        cores_per_socket = int(first.get("cpu cores", "1"))
    except ValueError:
        cores_per_socket = 1

    threads_per_core = 1
    try:
        siblings = int(first.get("siblings", str(cores_per_socket)))
        if cores_per_socket > 0:
            threads_per_core = max(1, math.ceil(siblings / cores_per_socket))
    except ValueError:
        threads_per_core = 1

    quantity = socket_count
    cores_per_cpu = max(1, cores_per_socket)
    threads = max(1, threads_per_core)
    logical_cpus = len(processors)

    # ── postcondition ──
    # The topology counts feed ``CPUDefinition`` fields that all carry ``ge=1``;
    # normalise them so a malformed /proc/cpuinfo can never construct an invalid
    # definition downstream, and pin ``logical_cpus`` to exactly one entry per
    # parsed processor block.
    assert quantity >= 1, quantity  # noqa: S101
    assert cores_per_cpu >= 1, cores_per_cpu  # noqa: S101
    assert threads >= 1, threads  # noqa: S101
    assert logical_cpus == len(processors), logical_cpus  # noqa: S101
    # ───────────────────

    return {
        "model_name": first.get("model name") or first.get("Processor") or "",
        "vendor": first.get("vendor_id") or first.get("Hardware") or "",
        "quantity": quantity,
        "cores_per_cpu": cores_per_cpu,
        "threads_per_core": threads,
        "architecture": platform.machine(),
        "logical_cpus": logical_cpus,
    }


def profile_cpus(cpuinfo_path: Path = Path("/proc/cpuinfo")) -> dict[str, CPUDefinition]:
    cpu = _parse_cpuinfo(cpuinfo_path)
    model_name = cpu.get("model_name") or platform.processor() or platform.machine()
    return {
        str(model_name): CPUDefinition(
            vendor=str(cpu.get("vendor") or ""),
            quantity=int(cpu.get("quantity") or 1),
            cores_per_cpu=int(cpu.get("cores_per_cpu") or 1),
            threads_per_core=int(cpu.get("threads_per_core") or 1),
            architecture=str(cpu.get("architecture") or platform.machine()),
            extra_info={
                "logical_cpus": int(cpu.get("logical_cpus") or os.cpu_count() or 1),
                "profile_source": "/proc/cpuinfo",
            },
        )
    }
