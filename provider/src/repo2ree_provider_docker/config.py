"""Environment-backed Docker provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from repo2ree_provider_docker.identity import load_or_create_provider_id


@dataclass(frozen=True)
class ProviderConfig:
    api_ws_url: str
    workbench_api_ws_url: str
    provider_id: str
    docker_mode: str = "dind"
    workbench_network: str = ""
    otlp_endpoint: str | None = None


def load_config() -> ProviderConfig:
    explicit_id = os.environ.get("PROVIDER_ID")
    provider_id = explicit_id or load_or_create_provider_id(
        Path(os.environ.get("PROVIDER_STATE_DIR", "~/.repo2ree-provider")).expanduser()
    )
    return ProviderConfig(
        api_ws_url=os.environ.get("PROVIDER_API_WS_URL", "ws://localhost:8000/provider/connect"),
        workbench_api_ws_url=os.environ.get("PROVIDER_WORKBENCH_API_WS_URL", "ws://localhost:8000/workbench/connect"),
        provider_id=provider_id,
        docker_mode=os.environ.get("PROVIDER_DOCKER_MODE", "dind"),
        workbench_network=os.environ.get("PROVIDER_WORKBENCH_DOCKER_NETWORK", ""),
        otlp_endpoint=os.environ.get("OTLP_ENDPOINT") or None,
    )
