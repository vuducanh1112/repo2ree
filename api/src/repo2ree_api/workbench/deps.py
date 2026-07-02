"""Module-level workbench manager singleton for use across API routes."""

from __future__ import annotations

from repo2ree_api.settings import service_settings
from repo2ree_api.workbench.catalog import default_workbench_image
from repo2ree_protocol.tracing import build_span_sink
from repo2ree_supervisor import (
    AgentConnectionRegistry,
    WorkbenchManager,
    WsAgentClient,
)
from repo2ree_supervisor.registry import WorkbenchRegistry

_registry = WorkbenchRegistry(service_settings.WORKBENCH_REGISTRY_FILE)

# The registry of agents that have dialed in. The WebSocket route (/agent/connect)
# populates it; WsAgentClient reads from it to drive whichever agent is connected.
agent_registry = AgentConnectionRegistry()

workbench_manager = WorkbenchManager(
    registry=_registry,
    # The catalog default, unless a deployment pins one via WORKBENCH_IMAGE.
    workbench_image=service_settings.WORKBENCH_IMAGE or default_workbench_image().ref,
    agent=WsAgentClient(agent_registry),
    span_sink=build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True),
)
