from __future__ import annotations

from pathlib import Path

from repo2ree_core.hbom.hbom import MemoryDefinition
from repo2ree_core.hbom.profiler_utils import round_gib


def profile_memory() -> dict[str, MemoryDefinition]:
    mem_total_kib = 0
    meminfo_path = Path("/proc/meminfo")
    if meminfo_path.exists():
        for line in meminfo_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("MemTotal:"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    mem_total_kib = int(parts[1])
                except ValueError:
                    mem_total_kib = 0
            break

    capacity_gb = round_gib(mem_total_kib * 1024)
    return {
        "Installed Memory": MemoryDefinition(
            quantity=1,
            capacity_gb=capacity_gb,
            memory_type="DDR5",
            speed_mt_s=0,
            extra_info={
                "aggregate": True,
                "profile_source": "/proc/meminfo",
            },
        )
    }
