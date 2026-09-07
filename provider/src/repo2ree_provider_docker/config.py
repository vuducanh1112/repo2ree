"""Environment-backed Docker provider configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    # What the benches this provider starts do with their own spans. They inherit
    # neither this process's OTLP_ENDPOINT nor its reachability: a bench may sit
    # on an isolated network where the collector this provider posts to does not
    # resolve. ``relay`` sends spans over the socket each bench already holds.
    # ``direct`` needs workbench_otlp_endpoint to name a collector *they* reach.
    workbench_telemetry: str = "relay"
    workbench_otlp_endpoint: str | None = None


class ProviderEnvironment(BaseSettings):
    """Validated environment accepted by the provider process.

    Uppercase fields intentionally match the external contract. The application
    converts this transport model into the domain-oriented ``ProviderConfig``.
    """

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

    PROVIDER_ID: str | None = None
    PROVIDER_STATE_DIR: Path = Path("~/.repo2ree-provider")
    PROVIDER_API_WS_URL: str = "ws://localhost:8000/provider/connect"
    PROVIDER_WORKBENCH_API_WS_URL: str = "ws://localhost:8000/workbench/connect"
    PROVIDER_LOCATION_ID: str | None = None
    PROVIDER_LOCATION_LABEL: str | None = None
    PROVIDER_ACCEPTS_CUSTOM_IMAGE: bool = True
    PROVIDER_DOCKER_MODE: Literal["dind", "host-socket"] = "dind"
    PROVIDER_WORKBENCH_DOCKER_NETWORK: str = ""
    PROVIDER_WORKBENCH_TELEMETRY: Literal["relay", "direct", "local", "off"] = "relay"
    PROVIDER_WORKBENCH_OTLP_ENDPOINT: str | None = None
    WORKBENCH_IMAGE_CATALOG: str | None = None
    OTLP_ENDPOINT: str | None = None

    @field_validator("PROVIDER_ACCEPTS_CUSTOM_IMAGE", mode="before")
    @classmethod
    def _blank_boolean_uses_default(cls, value: object) -> object:
        return True if value == "" else value

    @field_validator("PROVIDER_WORKBENCH_TELEMETRY", mode="before")
    @classmethod
    def _normalize_telemetry(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) and value.strip() else "relay"

    @field_validator("OTLP_ENDPOINT", "PROVIDER_WORKBENCH_OTLP_ENDPOINT", mode="before")
    @classmethod
    def _blank_endpoint_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _direct_telemetry_has_endpoint(self) -> ProviderEnvironment:
        if self.PROVIDER_WORKBENCH_TELEMETRY == "direct" and not self.PROVIDER_WORKBENCH_OTLP_ENDPOINT:
            raise ValueError("PROVIDER_WORKBENCH_OTLP_ENDPOINT is required when PROVIDER_WORKBENCH_TELEMETRY=direct")
        return self


def load_config() -> ProviderConfig:
    environment = ProviderEnvironment()
    explicit_id = environment.PROVIDER_ID
    provider_id = explicit_id or load_or_create_provider_id(environment.PROVIDER_STATE_DIR.expanduser())
    raw_catalog = environment.WORKBENCH_IMAGE_CATALOG
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
        api_ws_url=environment.PROVIDER_API_WS_URL,
        workbench_api_ws_url=environment.PROVIDER_WORKBENCH_API_WS_URL,
        provider_id=provider_id,
        location_id=environment.PROVIDER_LOCATION_ID or provider_id,
        location_label=environment.PROVIDER_LOCATION_LABEL or provider_id,
        images=images,
        accepts_custom_image=environment.PROVIDER_ACCEPTS_CUSTOM_IMAGE,
        docker_mode=environment.PROVIDER_DOCKER_MODE,
        workbench_network=environment.PROVIDER_WORKBENCH_DOCKER_NETWORK,
        otlp_endpoint=environment.OTLP_ENDPOINT,
        workbench_telemetry=environment.PROVIDER_WORKBENCH_TELEMETRY,
        workbench_otlp_endpoint=environment.PROVIDER_WORKBENCH_OTLP_ENDPOINT,
    )
