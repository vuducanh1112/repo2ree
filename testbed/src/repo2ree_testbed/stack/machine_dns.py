"""The DNS servers a machine's own daemon hands its containers and build steps.

A machine on a user-defined network resolves through Docker's embedded ``127.0.0.11``. A daemon nested
there cannot pass a loopback server on, so it falls back to public DNS, which a network that allows only
its own servers refuses: image pulls work, and every build step fails to resolve. A container on the host
daemon's default bridge is told the host's own servers, even when this process sees only ``127.0.0.11``.
"""

from __future__ import annotations

import ipaddress
import subprocess
from functools import lru_cache

# What dockerd falls back to when it was given only loopback servers: finding only these is finding nothing.
_DOCKER_FALLBACK = frozenset({"8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"})
_DISCOVERY_TIMEOUT_SECONDS = 60


def nameservers(resolv_conf: str) -> tuple[str, ...]:
    """The servers of a resolv.conf, in order, without loopback ones or dockerd's own fallback."""
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
    """The host's DNS servers, read from a container of ``image`` on its default bridge; () when it has none."""
    command = ["docker", "run", "--rm", "--network", "bridge", "--entrypoint", "cat", image, "/etc/resolv.conf"]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=_DISCOVERY_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(f"could not read the DNS servers of a bridge container of {image}: {result.stderr.strip()}")
    return nameservers(result.stdout)
