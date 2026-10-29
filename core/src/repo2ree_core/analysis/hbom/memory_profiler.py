from __future__ import annotations

from pathlib import Path

from repo2ree_ree.hbom import MemoryDefinition


def profile_memory(meminfo_path: Path = Path("/proc/meminfo")) -> dict[str, MemoryDefinition]:
    mem_total_kib = 0
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

    return {
        "Installed Memory": MemoryDefinition(
            quantity=1,
            capacity_bytes=max(mem_total_kib, 0) * 1024,
            memory_type="DDR5",
            speed_mt_s=0,
            extra_info={
                "aggregate": True,
                "profile_source": "/proc/meminfo",
            },
        )
    }
