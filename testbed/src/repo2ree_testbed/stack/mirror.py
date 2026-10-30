"""The machine's registry mirror: a pull-through cache of Docker Hub every e2e stack's benches pull through.

Each dind bench starts with an empty image store, so without a mirror every bench pulls
its base images from Docker Hub again. One mirror per machine, kept running across runs
with its cache on a volume, fetches each image once; benches reach it as their providers
are told (``PROVIDER_WORKBENCH_REGISTRY_MIRROR``).

Where the testbed runs in a container (the dev container), the mirror joins that
container's network and is addressed by name, as benches address the API. Otherwise it
publishes a port that benches reach through ``host.docker.internal``.

``REPO2REE_REGISTRY_MIRROR`` overrides it: ``off`` for none, or a URL to use instead.

``python -m repo2ree_testbed mirror warm`` fetches every image the example projects pin
by digest through the mirror ahead of a run (``just fetch-showcase``), each platform's
manifest, config, and layers, so a run on a warm machine pulls nothing from Docker Hub.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from repo2ree_testbed import provenance
from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.stack.docker import first_network, own_container
from repo2ree_testbed.stack.process import capture

NAME = "repo2ree-registry-mirror"
VOLUME = "repo2ree-registry-mirror"
# registry:2, by its multi-platform index digest.
IMAGE = "docker.io/library/registry@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
PORT = 5000
PUBLISHED_PORT = int(os.environ.get("REPO2REE_REGISTRY_MIRROR_PORT", "15000"))
UPSTREAM = "https://registry-1.docker.io"


def _running() -> bool:
    return capture(["docker", "inspect", "-f", "{{.State.Running}}", NAME]) == "true"


def _start(network: str) -> None:
    placement = ["--network", network] if network else ["-p", f"{PUBLISHED_PORT}:{PORT}"]
    result = subprocess.run(
        [
            *("docker", "run", "-d", "--name", NAME, "--restart", "unless-stopped"),
            *placement,
            *("-v", f"{VOLUME}:/var/lib/registry"),
            *("-e", f"REGISTRY_PROXY_REMOTEURL={UPSTREAM}"),
            IMAGE,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    # Stacks side by side race to start it; whichever lost finds it already there.
    if result.returncode != 0 and not _running():
        subprocess.run(["docker", "start", NAME], check=False, capture_output=True)
        if not _running():
            raise RuntimeError(f"could not start the registry mirror {NAME}: {result.stderr.strip()}")


def _join(network: str) -> None:
    joined = capture(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", NAME])
    if f'"{network}"' not in joined:
        subprocess.run(["docker", "network", "connect", network, NAME], check=False, capture_output=True)


def ensure() -> str:
    """The mirror URL benches should pull through, starting the mirror if it is not running; "" for none."""
    override = os.environ.get("REPO2REE_REGISTRY_MIRROR", "").strip()
    if override.lower() == "off":
        return ""
    if override:
        return override
    container = own_container()
    network = first_network(container) if container else ""
    if not _running():
        _start(network)
    if network:
        _join(network)
    _wait_ready()
    return f"http://{NAME}:{PORT}" if network else f"http://host.docker.internal:{PUBLISHED_PORT}"


def _wait_ready(attempts: int = 60) -> None:
    """Until the registry answers its API root, as it does once it listens."""
    for _ in range(attempts):
        try:
            with _open(f"{local_url()}/v2/"):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"the registry mirror {NAME} did not start answering")


def local_url() -> str:
    """The mirror as this process reaches it (by name in a container, else the published port)."""
    container = own_container()
    return f"http://{NAME}:{PORT}" if container and first_network(container) else f"http://127.0.0.1:{PUBLISHED_PORT}"


# A digest-pinned Docker Hub image in a Dockerfile: `FROM name[:tag]@sha256:…`.
_PINNED_FROM = re.compile(
    r"^FROM\s+(?:--platform=\S+\s+)?(?:docker\.io/)?([a-z0-9._/-]+)(?::[\w.-]+)?@(sha256:[0-9a-f]{64})", re.MULTILINE
)
_INDEX_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
_ACCEPT = ", ".join(
    (
        *_INDEX_TYPES,
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)
ALL_PLATFORMS = ("linux/amd64", "linux/arm64")


def pinned_images(root: Path = ROOT / "examples/projects") -> list[tuple[str, str]]:
    """(repository, digest) for every digest-pinned base image the example projects build from."""
    found: set[tuple[str, str]] = set()
    for dockerfile in sorted(root.glob("*/Dockerfile")):
        for name, digest in _PINNED_FROM.findall(dockerfile.read_text()):
            found.add((name if "/" in name else f"library/{name}", digest))
    return sorted(found)


def _open(url: str, accept: str = "") -> http.client.HTTPResponse:
    """A GET to the mirror; only http(s), as a registry URL is."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"not a registry URL: {url}")
    request = urllib.request.Request(url, headers={"Accept": accept} if accept else {})  # noqa: S310 - checked above
    response: http.client.HTTPResponse = urllib.request.urlopen(request, timeout=600)  # noqa: S310 - checked above
    return response


def _get(url: str, accept: str = "") -> bytes:
    with _open(url, accept) as response:
        return response.read()


def _fetch_blob(base: str, repository: str, digest: str) -> int:
    size = 0
    with _open(f"{base}/v2/{repository}/blobs/{digest}") as response:
        while chunk := response.read(1 << 20):
            size += len(chunk)
    return size


def warm(base: str, repository: str, digest: str, platforms: tuple[str, ...]) -> int:
    """Fetch one image through the mirror for each of ``platforms`` (``os/arch``); the bytes fetched."""
    manifest = json.loads(_get(f"{base}/v2/{repository}/manifests/{digest}", _ACCEPT))
    if manifest.get("mediaType") in _INDEX_TYPES or "manifests" in manifest:
        wanted = [
            entry["digest"]
            for entry in manifest["manifests"]
            if f"{entry.get('platform', {}).get('os')}/{entry.get('platform', {}).get('architecture')}" in platforms
        ]
    else:
        wanted = [digest]
    fetched = 0
    for platform_digest in wanted:
        image = json.loads(_get(f"{base}/v2/{repository}/manifests/{platform_digest}", _ACCEPT))
        for blob in [image["config"], *image.get("layers", [])]:
            fetched += _fetch_blob(base, repository, blob["digest"])
    return fetched


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed mirror")
    parser.add_argument("command", choices=("warm", "url"))
    parser.add_argument(
        "--all-platforms", action="store_true", help=f"warm {', '.join(ALL_PLATFORMS)}, not only this daemon's"
    )
    args = parser.parse_args()
    if not ensure():
        print("no registry mirror (REPO2REE_REGISTRY_MIRROR=off)")
        return 0
    base = os.environ.get("REPO2REE_REGISTRY_MIRROR") or local_url()
    if args.command == "url":
        print(base)
        return 0
    platforms = ALL_PLATFORMS if args.all_platforms else (provenance.platform(),)
    for repository, digest in pinned_images():
        try:
            fetched = warm(base, repository, digest, platforms)
        except OSError as error:
            print(f"could not warm {repository}@{digest}: {error}", file=sys.stderr)
            return 1
        print(f">> {repository}@{digest[:19]}: {fetched / 1e6:.0f} MB through the mirror")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
