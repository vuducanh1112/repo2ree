"""Fleet view: the workbench agents currently dialed into the control plane.

Read-only. An agent appears here for exactly as long as it holds its outbound
WebSocket (``/agent/connect``); the registry drops it on disconnect, so presence
in this list *is* liveness. This is the control-plane surface behind the
frontend's agent-management pane.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from repo2ree_api.workbench.deps import agent_registry

agents_router = APIRouter()


class AgentSummary(BaseModel):
    agentId: str
    hostname: str
    version: str
    dockerMode: str
    # ISO 8601 UTC; when the agent dialed in.
    connectedAt: str
    status: str = "connected"


class AgentList(BaseModel):
    agents: list[AgentSummary]


@agents_router.get("/api/v1/agents")
def list_agents() -> AgentList:
    """Every workbench agent currently connected to this control plane."""
    agents = [
        AgentSummary(
            agentId=info.agent_id,
            hostname=info.hostname,
            version=info.version,
            dockerMode=info.docker_mode,
            connectedAt=datetime.fromtimestamp(info.connected_at, tz=UTC).isoformat(),
        )
        for info in agent_registry.list_agents()
    ]
    return AgentList(agents=agents)
