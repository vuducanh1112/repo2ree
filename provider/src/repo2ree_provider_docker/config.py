"""Environment-backed Docker provider configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from repo2ree_provider_docker.identity import load_or_create_provider_id

_DEFAULT_IMAGE = (
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515"
)


@dataclass(frozen=True)
class PrivateProfile:
    id: str
    revision: str
    image: str
    label: str
    description: str = ""
    # What this image actually supplies. A provider may offer both a Docker
    # workbench and a plain one, so the substrate belongs to the profile rather
    # than to the daemon mode the provider itself runs in; unset means "whatever
    # this provider's docker_mode implies".
    substrate: str | None = None


@dataclass(frozen=True)
class ProviderConfig:
    api_ws_url: str
    workbench_api_ws_url: str
    provider_id: str
    location_id: str
    location_label: str
    profiles: tuple[PrivateProfile, ...]
    docker_mode: str = "dind"
    workbench_network: str = ""
    otlp_endpoint: str | None = None


def load_config() -> ProviderConfig:
    explicit_id = os.environ.get("PROVIDER_ID")
    provider_id = explicit_id or load_or_create_provider_id(
        Path(os.environ.get("PROVIDER_STATE_DIR", "~/.repo2ree-provider")).expanduser()
    )
    raw_catalog = os.environ.get("PROVIDER_PROFILE_CATALOG")
    if raw_catalog:
        profiles = tuple(PrivateProfile(**item) for item in json.loads(raw_catalog))
    else:
        # Temporary deployment-config compatibility: old stacks may still set
        # the image catalog globally. It is interpreted only here, on the
        # provider side, and never accepted in an allocation request.
        legacy = json.loads(os.environ.get("WORKBENCH_IMAGE_CATALOG", "[]"))
        image = str(legacy[0]["ref"]) if legacy else _DEFAULT_IMAGE
        profiles = (
            PrivateProfile(
                id="standard",
                revision="1",
                image=image,
                label="Standard Docker workbench",
                description="A fixed deployment-managed Docker workbench.",
            ),
        )
    if not profiles:
        raise ValueError("PROVIDER_PROFILE_CATALOG must contain at least one profile")
    keys = [(profile.id, profile.revision) for profile in profiles]
    if len(keys) != len(set(keys)):
        raise ValueError("provider profile id/revision pairs must be unique")
    return ProviderConfig(
        api_ws_url=os.environ.get("PROVIDER_API_WS_URL", "ws://localhost:8000/provider/connect"),
        workbench_api_ws_url=os.environ.get("PROVIDER_WORKBENCH_API_WS_URL", "ws://localhost:8000/workbench/connect"),
        provider_id=provider_id,
        location_id=os.environ.get("PROVIDER_LOCATION_ID", provider_id),
        location_label=os.environ.get("PROVIDER_LOCATION_LABEL", provider_id),
        profiles=profiles,
        docker_mode=os.environ.get("PROVIDER_DOCKER_MODE", "dind"),
        workbench_network=os.environ.get("PROVIDER_WORKBENCH_DOCKER_NETWORK", ""),
        otlp_endpoint=os.environ.get("OTLP_ENDPOINT") or None,
    )
