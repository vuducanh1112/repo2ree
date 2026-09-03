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
class CuratedImage:
    """One entry of this provider's published catalog.

    Only ``ref`` is meaningful to provisioning; the rest names the entry for the
    author's picker. Nothing here says what the image *supplies* — that is the
    image's business and the build's problem, not a fact this provider asserts.
    """

    ref: str
    id: str = ""
    label: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.ref:
            raise ValueError("a catalog entry needs a ref")
        # A ref uniquely identifies an entry, so it doubles as a stable id and a
        # fallback label; that is what lets an entry be just {"ref": ...}.
        object.__setattr__(self, "id", self.id or self.ref)
        object.__setattr__(self, "label", self.label or self.ref)


@dataclass(frozen=True)
class ProviderConfig:
    api_ws_url: str
    workbench_api_ws_url: str
    provider_id: str
    location_id: str
    location_label: str
    images: tuple[CuratedImage, ...]
    # Whether this provider will run a ref that is not in its catalog. The
    # curated set is a recommendation, not a jail: a deployment that wants one
    # sets this false.
    accepts_custom_image: bool = True
    docker_mode: str = "dind"
    workbench_network: str = ""
    otlp_endpoint: str | None = None


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def load_config() -> ProviderConfig:
    explicit_id = os.environ.get("PROVIDER_ID")
    provider_id = explicit_id or load_or_create_provider_id(
        Path(os.environ.get("PROVIDER_STATE_DIR", "~/.repo2ree-provider")).expanduser()
    )
    raw_catalog = os.environ.get("WORKBENCH_IMAGE_CATALOG")
    if raw_catalog:
        images = tuple(CuratedImage(**item) for item in json.loads(raw_catalog))
    else:
        images = (
            CuratedImage(
                id="standard",
                ref=_DEFAULT_IMAGE,
                label="Standard (docker)",
                description="Lean docker-in-docker bench; the provider injects the executor and base tools.",
            ),
        )
    if not images:
        raise ValueError("WORKBENCH_IMAGE_CATALOG must contain at least one image")
    ids = [image.id for image in images]
    if len(ids) != len(set(ids)):
        raise ValueError("catalog image ids must be unique")
    return ProviderConfig(
        api_ws_url=os.environ.get("PROVIDER_API_WS_URL", "ws://localhost:8000/provider/connect"),
        workbench_api_ws_url=os.environ.get("PROVIDER_WORKBENCH_API_WS_URL", "ws://localhost:8000/workbench/connect"),
        provider_id=provider_id,
        location_id=os.environ.get("PROVIDER_LOCATION_ID", provider_id),
        location_label=os.environ.get("PROVIDER_LOCATION_LABEL", provider_id),
        images=images,
        accepts_custom_image=_env_flag("PROVIDER_ACCEPTS_CUSTOM_IMAGE", True),
        docker_mode=os.environ.get("PROVIDER_DOCKER_MODE", "dind"),
        workbench_network=os.environ.get("PROVIDER_WORKBENCH_DOCKER_NETWORK", ""),
        otlp_endpoint=os.environ.get("OTLP_ENDPOINT") or None,
    )
