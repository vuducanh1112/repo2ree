"""Run the workbench agent.

The agent is outbound-only: it dials the control plane at ``WORKBENCH_API_WS_URL``
and serves requests over that single connection. It never listens on a port, so
it works from inside clusters and NATed networks that only permit egress.

``WORKBENCH_DOCKER_MODE`` selects the container runtime mode (``dind`` or
``host-socket``).

Identity: the control plane pins each REE to the agent that provisioned it, so
the id must be stable across restarts. By default the agent mints one on first
start and persists it under ``WORKBENCH_AGENT_STATE_DIR`` (default
``~/.repo2ree``); a containerized agent must volume-mount that dir or its id —
and the reachability of its REEs — resets with the container. Set
``WORKBENCH_AGENT_ID`` to manage identity explicitly instead (never persisted).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from repo2ree_agent.control_link import run_agent
from repo2ree_agent.identity import load_or_create_agent_id


def _resolve_agent_id() -> str:
    explicit = os.environ.get("WORKBENCH_AGENT_ID")
    if explicit:
        return explicit
    state_dir = Path(os.environ.get("WORKBENCH_AGENT_STATE_DIR", "~/.repo2ree")).expanduser()
    return load_or_create_agent_id(state_dir)


def main() -> None:
    api_ws_url = os.environ.get("WORKBENCH_API_WS_URL", "ws://localhost:8000/agent/connect")
    docker_mode = os.environ.get("WORKBENCH_DOCKER_MODE", "dind")
    asyncio.run(run_agent(api_ws_url, docker_mode, _resolve_agent_id()))


if __name__ == "__main__":
    main()
