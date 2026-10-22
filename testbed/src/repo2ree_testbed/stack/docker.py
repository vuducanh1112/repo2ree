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


def networks(container: str) -> dict[str, Network]:
    output = capture(["docker", "inspect", "-f", "{{json .NetworkSettings.Networks}}", container])
    try:
        return _NETWORKS.validate_json(output) if output else {}
    except ValidationError:
        return {}


def first_network(container: str) -> str:
    return next(iter(networks(container)), "")
