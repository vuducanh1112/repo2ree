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
from repo2ree_protocol.log import configure_logging
from repo2ree_protocol.tracing import otlp_log_handler, setup_logs, setup_metrics, setup_tracing


def _resolve_agent_id() -> str:
    explicit = os.environ.get("WORKBENCH_AGENT_ID")
    if explicit:
        return explicit
    state_dir = Path(os.environ.get("WORKBENCH_AGENT_STATE_DIR", "~/.repo2ree")).expanduser()
    return load_or_create_agent_id(state_dir)


def main() -> None:
    otlp_endpoint = os.environ.get("OTLP_ENDPOINT") or None
    logger_provider = setup_logs("repo2ree-agent", endpoint=otlp_endpoint)
    configure_logging(
        structured=otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    tracer_provider = setup_tracing("repo2ree-agent", endpoint=otlp_endpoint, console_fallback=True)
    meter_provider = setup_metrics("repo2ree-agent", endpoint=otlp_endpoint)
    api_ws_url = os.environ.get("WORKBENCH_API_WS_URL", "ws://localhost:8000/agent/connect")
    docker_mode = os.environ.get("WORKBENCH_DOCKER_MODE", "dind")
    try:
        asyncio.run(run_agent(api_ws_url, docker_mode, _resolve_agent_id()))
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()


if __name__ == "__main__":
    main()
