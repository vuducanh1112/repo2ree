"""Environment-backed process configuration for the workbench agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from repo2ree_agent.identity import load_or_create_agent_id


@dataclass(frozen=True)
class DockerConfig:
    mode: str = "dind"


@dataclass(frozen=True)
class AgentConfig:
    api_ws_url: str
    agent_id: str
    docker: DockerConfig
    otlp_endpoint: str | None = None


def load_config() -> AgentConfig:
    explicit_id = os.environ.get("WORKBENCH_AGENT_ID")
    if explicit_id:
        agent_id = explicit_id
    else:
        state_dir = Path(os.environ.get("WORKBENCH_AGENT_STATE_DIR", "~/.repo2ree")).expanduser()
        agent_id = load_or_create_agent_id(state_dir)
    return AgentConfig(
        api_ws_url=os.environ.get("WORKBENCH_API_WS_URL", "ws://localhost:8000/agent/connect"),
        agent_id=agent_id,
        docker=DockerConfig(mode=os.environ.get("WORKBENCH_DOCKER_MODE", "dind")),
        otlp_endpoint=os.environ.get("OTLP_ENDPOINT") or None,
    )
