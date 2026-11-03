"""What Docker says about the container this process runs in, and the networks containers share."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from repo2ree_testbed.stack.process import capture


class Network(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    Gateway: str = ""


_NETWORKS = TypeAdapter[dict[str, Network]](dict[str, Network])


def own_container() -> str | None:
    hostname = os.getenv("HOSTNAME", "")
    return hostname if hostname and Path("/.dockerenv").is_file() else None


def engine_path(path: Path) -> str:
    """``LOCAL=ENGINE``: where the engine finds ``path``, when this process runs in a container beside it.

    Blank when the engine sees this process's files where it does (no container, or no mount holds it).
    """
    container = own_container()
    if container is None:
        return ""
    mounts = capture(["docker", "inspect", "-f", "{{range .Mounts}}{{.Destination}}={{.Source}};{{end}}", container])
    for mount in filter(None, (mounts or "").split(";")):
        local, _, source = mount.partition("=")
        if path.resolve().is_relative_to(local):
            return f"{local}={source}"
    return ""


def networks(container: str) -> dict[str, Network]:
    output = capture(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", container])
    try:
        return _NETWORKS.validate_json(output) if output else {}
    except ValidationError:
        return {}


def first_network(container: str) -> str:
    return next(iter(networks(container)), "")
