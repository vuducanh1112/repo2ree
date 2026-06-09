from __future__ import annotations

import json
import math
from typing import Literal

from repo2ree_core.domain.hbom import StorageDefinition
from repo2ree_core.hbom.profiler_utils import round_gib, run_command

StorageType = Literal["HDD", "SSD", "NVMe", "eMMC", "SD"]


def _storage_type_for_device(name: str, rotational: str, transport: str, model_name: str) -> tuple[StorageType, str]:
    lowered_name = name.lower()
    lowered_transport = transport.lower()
    lowered_model = model_name.lower()

    if lowered_name.startswith("nvme") or "nvme" in lowered_transport:
        return "NVMe", "NVMe"
    if lowered_name.startswith("mmcblk"):
        if "sd" in lowered_model:
            return "SD", "SD"
        return "eMMC", "eMMC"
    if rotational == "1":
        return "HDD", transport.upper() if transport else ""
    return "SSD", transport.upper() if transport else ""


def profile_storage() -> dict[str, StorageDefinition]:
    result: dict[str, StorageDefinition] = {}
    completed = run_command(
        "lsblk",
        "-b",
        "-J",
        "-d",
        "-o",
        "NAME,MODEL,VENDOR,SIZE,ROTA,TRAN,TYPE",
    )
    if not completed or completed.returncode != 0 or not completed.stdout.strip():
        return result

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return result

    for device in payload.get("blockdevices") or []:
        if str(device.get("type") or "") != "disk":
            continue

        name = str(device.get("name") or "").strip()
        model_name = str(device.get("model") or "").strip() or name
        vendor = str(device.get("vendor") or "").strip()
        size_bytes = int(device.get("size") or 0)
        transport = str(device.get("tran") or "").strip()
        rotational = str(device.get("rota") or "").strip()
        storage_type, interface = _storage_type_for_device(
            name=name,
            rotational=rotational,
            transport=transport,
            model_name=model_name,
        )
        key = model_name
        if key in result and math.isclose(
            result[key].capacity_gb,
            round_gib(size_bytes),
            rel_tol=0,
            abs_tol=0.01,
        ):
            result[key].quantity += 1
            continue

        if key in result:
            key = f"{model_name} ({name})"

        result[key] = StorageDefinition(
            vendor=vendor,
            quantity=1,
            capacity_gb=round_gib(size_bytes),
            storage_type=storage_type,
            interface=interface,
            extra_info={
                "device": name,
                "transport": transport or None,
                "profile_source": "lsblk",
            },
        )
    return result
