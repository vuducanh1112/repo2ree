from __future__ import annotations

from repo2ree_core.hbom.hbom import GPUDefinition
from repo2ree_core.hbom.profiler_utils import run_command


def profile_gpus() -> dict[str, GPUDefinition]:
    result: dict[str, GPUDefinition] = {}

    nvidia = _run_nvidia_smi()
    if nvidia:
        return nvidia

    lspci = run_command("lspci")
    if not lspci or lspci.returncode != 0:
        return result

    for line in lspci.stdout.splitlines():
        lowered = line.lower()
        if (
            "vga compatible controller" not in lowered
            and "3d controller" not in lowered
        ):
            continue
        details = line.split(":", 2)[-1].strip()
        if not details:
            continue
        vendor = ""
        for candidate in ("NVIDIA", "AMD", "Advanced Micro Devices", "Intel"):
            if candidate.lower() in details.lower():
                vendor = "AMD" if candidate == "Advanced Micro Devices" else candidate
                break
        model_name = details
        if model_name in result:
            result[model_name].quantity += 1
            continue
        result[model_name] = GPUDefinition(
            vendor=vendor,
            quantity=1,
            interface="PCIe",
            extra_info={"profile_source": "lspci"},
        )
    return result


def _run_nvidia_smi() -> dict[str, GPUDefinition]:
    result: dict[str, GPUDefinition] = {}
    completed = run_command(
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version,pci.bus_id",
        "--format=csv,noheader,nounits",
    )
    if not completed or completed.returncode != 0:
        return result

    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        model_name, memory_mb, driver_version, bus_id = parts[:4]
        if model_name in result:
            result[model_name].quantity += 1
            continue
        memory_gb = 0.0
        try:
            memory_gb = round(float(memory_mb) / 1024, 2)
        except ValueError:
            memory_gb = 0.0
        result[model_name] = GPUDefinition(
            vendor="NVIDIA",
            quantity=1,
            memory_gb=memory_gb,
            interface="PCIe",
            extra_info={
                "driver_version": driver_version,
                "pci_bus_id": bus_id,
                "profile_source": "nvidia-smi",
            },
        )
    return result
