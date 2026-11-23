from __future__ import annotations

import ipaddress
import subprocess
from functools import lru_cache

_DOCKER_FALLBACK = frozenset({"8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"})
_DISCOVERY_TIMEOUT_SECONDS = 60


def nameservers(resolv_conf: str) -> tuple[str, ...]:
    found: list[str] = []
    for line in resolv_conf.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] != "nameserver":
            continue
        try:
            address = ipaddress.ip_address(fields[1].split("%", 1)[0])
        except ValueError:
            continue
        if not address.is_loopback:
            found.append(fields[1])
    return () if set(found) <= _DOCKER_FALLBACK else tuple(found)


@lru_cache
def host_nameservers(image: str) -> tuple[str, ...]:
    command = ["docker", "run", "--rm", "--network", "bridge", "--entrypoint", "cat", image, "/etc/resolv.conf"]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=_DISCOVERY_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(f"could not read the DNS servers of a bridge container of {image}: {result.stderr.strip()}")
    return nameservers(result.stdout)
