"""Module-level control-plane singletons shared across API routes.

The composition root: builds the workbench registry, the registry of dialed-in
agents, and the manager that drives workbenches through those agents.
"""

from __future__ import annotations

from repo2ree_api.settings import service_settings
from repo2ree_api.workbench_images import default_workbench_image
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
    # The catalog default; per-REE overrides come in on the provision request.
    workbench_image=default_workbench_image().ref,
    agent=WsAgentClient(agent_registry),
    span_sink=build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True),
)
