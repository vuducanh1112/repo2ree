"""What a dind bench's own daemon is configured with: its resolvers, and a registry mirror.

A bench on a user-defined network resolves through Docker's embedded
``127.0.0.11``. The nested ``dockerd`` cannot pass a loopback resolver on to
its own containers, so it falls back to public DNS (8.8.8.8 and friends) — and
on a network that allows only its own resolver, every ``RUN pip install`` and
``apt-get`` inside the bench fails to resolve while image pulls (resolved by the
daemon itself, through the bench) still work. The provider closes that gap by
writing ``dns`` into the bench's ``/etc/docker/daemon.json``.

The resolvers come from ``PROVIDER_WORKBENCH_DNS``: ``auto`` (the default) asks
the host daemon what a container on its default bridge gets — the host's own
non-loopback resolvers, systemd-resolved handled — which holds even when the
provider itself runs in a container on a user-defined network and sees only
``127.0.0.11``. ``off`` leaves benches as they were; anything else is a
comma-separated list of resolver addresses.

``PROVIDER_WORKBENCH_REGISTRY_MIRROR`` names a pull-through registry every bench
daemon pulls Docker Hub images through, so base images are fetched once per
machine rather than once per bench (each bench's image store starts empty).
"""

from __future__ import annotations

import io
import ipaddress
import json
import subprocess
import tarfile
from dataclasses import dataclass
from urllib.parse import urlsplit

from repo2ree_docker.ops import docker_op

# What dockerd falls back to when the resolv.conf it was given names only
# loopback resolvers. A discovery that finds only these found nothing.
DOCKER_FALLBACK_RESOLVERS = frozenset({"8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"})
_DAEMON_JSON = "/etc/docker/daemon.json"
_DISCOVERY_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class BenchDns:
    """Resolvers for bench daemons, and where they came from (for the log line saying so)."""

    resolvers: tuple[str, ...]
    source: str

    def describe(self) -> str:
        return f"{', '.join(self.resolvers)} ({self.source})"


def parse_setting(value: str) -> tuple[str, ...] | None:
    """``auto`` → None (discover); ``off`` → (); a comma-separated list → those addresses, validated."""
    setting = value.strip().lower()
    if setting in {"", "auto"}:
        return None
    if setting == "off":
        return ()
    resolvers = tuple(part.strip() for part in value.split(",") if part.strip())
    for resolver in resolvers:
        try:
            ipaddress.ip_address(resolver)
        except ValueError as exc:
            raise ValueError(f"PROVIDER_WORKBENCH_DNS: {resolver!r} is not an IP address (or auto, or off)") from exc
    return resolvers


def nameservers(resolv_conf: str) -> tuple[str, ...]:
    """The nameserver addresses of a resolv.conf, in order, without loopback ones."""
    found = []
    for line in resolv_conf.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "nameserver":
            try:
                address = ipaddress.ip_address(fields[1].split("%", 1)[0])
            except ValueError:
                continue
            if not address.is_loopback:
                found.append(fields[1])
    return tuple(found)


def discovered(resolv_conf: str) -> tuple[str, ...]:
    """The host's resolvers as a bridge container sees them; () when that is only dockerd's own fallback."""
    servers = nameservers(resolv_conf)
    return () if set(servers) <= DOCKER_FALLBACK_RESOLVERS else servers


def discover(image: str) -> tuple[str, ...]:
    """Ask the host daemon which resolvers a container on its default bridge gets.

    Runs ``cat`` from ``image`` (already pulled for the bench). Raises
    RuntimeError when that cannot be done; returns () when it found nothing
    better than dockerd's fallback.
    """
    with docker_op("docker.discover_dns"):
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--network", "bridge", "--entrypoint", "cat", image, "/etc/resolv.conf"],
                check=False,
                capture_output=True,
                text=True,
                timeout=_DISCOVERY_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"could not read a bridge container's resolv.conf: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["no output"]
        raise RuntimeError(f"could not read a bridge container's resolv.conf from {image}: {detail[0]}")
    return discovered(result.stdout)


def registry_mirror_settings(mirror: str) -> dict[str, object]:
    """``registry-mirrors`` for a mirror URL, and ``insecure-registries`` too when it is plain HTTP."""
    if not mirror:
        return {}
    parsed = urlsplit(mirror)
    settings: dict[str, object] = {"registry-mirrors": [mirror]}
    if parsed.scheme == "http":
        settings["insecure-registries"] = [parsed.netloc]
    return settings


def parse_registry_mirror(value: str) -> str:
    """A registry mirror URL, validated: http or https, with a host; "" for none."""
    mirror = value.strip().rstrip("/")
    if not mirror:
        return ""
    parsed = urlsplit(mirror)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query:
        raise ValueError(f"PROVIDER_WORKBENCH_REGISTRY_MIRROR: {value!r} is not an http(s)://host[:port] URL")
    return mirror


def merged_daemon_json(existing: bytes | None, settings: dict[str, object]) -> bytes:
    """The image's own daemon.json, if any, with ``settings`` set; every other setting kept."""
    config: dict[str, object] = {}
    if existing:
        try:
            parsed = json.loads(existing)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            config = parsed
    config.update(settings)
    return (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()


def _read_daemon_json(container: str) -> bytes | None:
    """The created container's own /etc/docker/daemon.json, or None if the image has none."""
    result = subprocess.run(
        ["docker", "cp", f"{container}:{_DAEMON_JSON}", "-"], check=False, capture_output=True, timeout=60
    )
    if result.returncode != 0:
        return None
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        member = next((entry for entry in archive.getmembers() if entry.isfile()), None)
        extracted = archive.extractfile(member) if member is not None else None
        return extracted.read() if extracted is not None else None


def _daemon_json_archive(content: bytes) -> bytes:
    """A tar of ``docker/daemon.json``, to unpack at the container's /etc (creating /etc/docker if absent)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        directory = tarfile.TarInfo("docker")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        entry = tarfile.TarInfo("docker/daemon.json")
        entry.size = len(content)
        entry.mode = 0o644
        archive.addfile(entry, io.BytesIO(content))
    return buffer.getvalue()


def write_daemon_settings(container: str, settings: dict[str, object]) -> None:
    """Set ``settings`` in a created, not yet started, container's daemon.json.

    ``docker cp`` addresses the container's filesystem through the daemon, so
    this needs no path shared between the provider and the daemon's host — a
    provider in a container, with the host's socket mounted, works the same.
    """
    with docker_op("docker.write_daemon_json"):
        content = merged_daemon_json(_read_daemon_json(container), settings)
        result = subprocess.run(
            ["docker", "cp", "-", f"{container}:/etc"],
            input=_daemon_json_archive(content),
            check=False,
            capture_output=True,
            timeout=60,
        )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or "no output"
        raise RuntimeError(f"could not write {_DAEMON_JSON} into {container}: {detail}")
