"""The agent plane's HTTP surface: where agents dial in, and the fleet view.

``/agent/connect`` is the WebSocket endpoint a workbench agent dials and holds
open; the control plane pushes ``WsRequest`` commands down it and receives
``WsMessage`` response frames. The route owns the async I/O and bridges it to
the synchronous ``AgentConnection`` that ``WsAgentClient`` drives: ``send_text``
schedules a send on the loop, and each inbound message is handed to
``on_message``.

``/api/v1/agents`` is the read-only fleet view. An agent appears there for
exactly as long as it holds its socket; the registry drops it on disconnect, so
presence in the list *is* liveness. This is the control-plane surface behind
the frontend's agent-management pane.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import agent_registry
from repo2ree_protocol.agent import ws_hello_adapter
from repo2ree_supervisor import AgentConnection

logger = logging.getLogger(__name__)


# ================================================
# Agent dial-in socket
# ================================================


agent_ws_router = APIRouter(tags=["fleet"])


@agent_ws_router.websocket("/agent/connect", name="connectRuntimeAgent")
async def agent_connect(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    connection: AgentConnection | None = None

    def on_send_done(fut: Future[None]) -> None:
        if fut.cancelled() or fut.exception() is None:
            return
        # A failed write means the socket is dying. Close the bridge now so
        # blocked callers get an unavailable error immediately, rather than
        # silently losing their request and waiting out the frame-gap timeout.
        logger.warning("send to workbench agent failed; closing its connection: %s", fut.exception())
        if connection is not None:
            connection.close()

    def send_text(text: str) -> None:
        # Called from a worker thread (the synchronous manager); hop back onto
        # the event loop to actually write to the socket.
        future = asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)
        future.add_done_callback(on_send_done)

    # First message is the agent's hello: identity + self-reported capabilities.
    hello = ws_hello_adapter.validate_json(await websocket.receive_text())
    connection = AgentConnection(send_text=send_text, hello=hello)
    agent_registry.register(hello.agent_id, connection)
    try:
        while True:
            connection.on_message(await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        connection.close()
        agent_registry.unregister(hello.agent_id, connection)


# ================================================
# Fleet view
# ================================================


agents_router = APIRouter(tags=["fleet"])


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


@agents_router.get(
    "/api/v1/agents",
    operation_id="listAgents",
    response_model=AgentList,
    responses=ERROR_RESPONSES,
)
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
