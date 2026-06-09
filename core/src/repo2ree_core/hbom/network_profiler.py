from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from repo2ree_core.domain.hbom import NetworkDefinition
from repo2ree_core.hbom.profiler_utils import read_optional_int, read_optional_text

NetworkType = Literal["ethernet", "infiniband", "wifi", "cellular"]


def _read_network_driver(interface_name: str) -> str:
    driver_link = Path(f"/sys/class/net/{interface_name}/device/driver")
    try:
        return driver_link.resolve().name
    except OSError:
        return ""


def profile_network() -> dict[str, NetworkDefinition]:
    result: dict[str, NetworkDefinition] = {}
    net_root = Path("/sys/class/net")
    if not net_root.exists():
        return result

    for iface_dir in net_root.iterdir():
        interface_name = iface_dir.name
        if interface_name == "lo":
            continue

        speed_mbps = read_optional_int(iface_dir / "speed")
        iface_type = read_optional_text(iface_dir / "type")
        wireless = (iface_dir / "wireless").exists()
        infiniband = (iface_dir / "device" / "infiniband").exists()
        driver_name = _read_network_driver(interface_name)

        network_type: NetworkType = "ethernet"
        if wireless:
            network_type = "wifi"
        elif infiniband or iface_type == "32":
            network_type = "infiniband"

        bandwidth_gbps = 0.0
        if speed_mbps and speed_mbps > 0:
            bandwidth_gbps = round(speed_mbps / 1000, 2)

        model_name = driver_name or interface_name
        key = model_name
        if key in result and math.isclose(result[key].bandwidth_gbps, bandwidth_gbps, rel_tol=0, abs_tol=0.01):
            result[key].quantity += 1
            continue
        if key in result:
            key = interface_name

        result[key] = NetworkDefinition(
            quantity=1,
            bandwidth_gbps=bandwidth_gbps,
            network_type=network_type,
            interface=driver_name,
            extra_info={
                "device": interface_name,
                "speed_mbps": speed_mbps,
                "profile_source": "/sys/class/net",
            },
        )
    return result
