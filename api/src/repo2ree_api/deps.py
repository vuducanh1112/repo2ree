"""Module-level control-plane singletons shared across API routes.

The composition root: builds the workbench registry, the registry of dialed-in
agents, the manager that drives workbenches through those agents, and the REE
index.

The first three are liveness state and die with the process that holds them.
The index does not — it is the one singleton here whose file must survive the
service, so it is built from its own configured path rather than derived from
anything running.
"""

from __future__ import annotations

from repo2ree_api.ree_index import ReeIndex
from repo2ree_api.settings import default_workbench_image, service_settings
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

# The durable record of what has been sealed here and where it was deposited.
# Written at seal, appended to when a deposit publishes, and read by anything
# that lists or exports the index.
ree_index = ReeIndex(service_settings.REE_INDEX_FILE)
