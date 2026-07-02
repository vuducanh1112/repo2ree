"""WebSocket endpoint where workbench agents dial in (Step 1).

The agent connects outbound and holds this socket open; the control plane pushes
``WsRequest`` commands down it and receives ``WsMessage`` response frames. This
route owns the async I/O and bridges it to the synchronous ``AgentConnection``
that ``WsAgentClient`` drives: ``send_text`` schedules a send on the loop, and
each inbound message is handed to ``on_message``.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from repo2ree_api.workbench.deps import agent_registry
from repo2ree_protocol.agent import ws_hello_adapter
from repo2ree_supervisor import AgentConnection

agent_ws_router = APIRouter()


@agent_ws_router.websocket("/agent/connect")
async def agent_connect(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()

    def send_text(text: str) -> None:
        # Called from a worker thread (the synchronous manager); hop back onto
        # the event loop to actually write to the socket.
        asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)

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
