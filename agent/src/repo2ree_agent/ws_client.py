"""Agent-dialed WebSocket mode (Step 1): outbound-only, no listening port.

The agent dials the control plane, sends a hello, then serves ``WsRequest``
messages that arrive over the same connection — the control plane pushes work
down the agent-initiated socket. Each request is handled concurrently; its
response frames are tagged with the request id and streamed back.

``DockerRuntime`` is synchronous (blocking subprocess + generators), so blocking
work runs in a thread (``asyncio.to_thread``) and streaming ops pump their sync
generator from a thread into the event loop, forwarding each frame as it arrives.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.metadata
import logging
import socket
import threading
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import websockets
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect

from repo2ree_agent.docker_runtime import DockerRuntime, WorkbenchGone
from repo2ree_agent.transfers import TransferStore
from repo2ree_protocol.agent import (
    COPY_CHUNK_BYTES,
    AgentFrame,
    AgentHello,
    BytesChunkFrame,
    CopyAbortRequest,
    CopyChunkRequest,
    CopyCloseRequest,
    CopyOpenRequest,
    DoneFrame,
    ErrorFrame,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    IsRunningRequest,
    ProvisionRequest,
    RemoveRequest,
    ReprovisionRequest,
    RunningFrame,
    TransferFrame,
    UnavailableFrame,
    WsMessage,
    ws_request_adapter,
)

logger = logging.getLogger(__name__)

_STREAM_END = object()


# ================================================
# Connection loop
# ================================================


def _agent_version() -> str:
    try:
        return importlib.metadata.version("repo2ree-agent")
    except importlib.metadata.PackageNotFoundError:
        return ""


async def run_agent(api_ws_url: str, docker_mode: str, agent_id: str, *, reconnect_delay: float = 3.0) -> None:
    """Dial the control plane and serve requests, reconnecting on drop."""
    runtime = DockerRuntime(docker_mode)
    hello = AgentHello(
        agent_id=agent_id,
        hostname=socket.gethostname(),
        version=_agent_version(),
        docker_mode=docker_mode,
        # Minted once per process: reconnects reuse it, so the control plane can
        # tell this instance reconnecting from another instance claiming its id.
        nonce=uuid4().hex,
    )
    while True:
        try:
            async with connect(api_ws_url) as ws:
                logger.info("agent %s connected to %s", agent_id, api_ws_url)
                await ws.send(hello.model_dump_json())
                await _serve(ws, runtime)
        except (OSError, websockets.WebSocketException) as exc:
            logger.warning("agent connection to %s lost (%s); retrying", api_ws_url, exc)
            await asyncio.sleep(reconnect_delay)


# ================================================
# Request dispatch
# ================================================


async def _serve(ws: ClientConnection, runtime: DockerRuntime) -> None:
    # Chunked copy-in transfers are scoped to this connection; if it drops with
    # any still open, their partial temp files are discarded rather than leaked.
    transfers = TransferStore()
    # Hold a strong reference to every in-flight handler: the event loop only
    # keeps a weak one, so a task dropped here could be garbage-collected
    # mid-request — silently losing its response and hanging the caller.
    tasks: set[asyncio.Task[None]] = set()
    try:
        async for message in ws:
            text = message if isinstance(message, str) else message.decode()
            # A malformed request (say, a version-skewed control plane) must not
            # tear down the socket and abort every in-flight call — drop the one
            # message and keep serving. Per-op arg validation already fails soft
            # inside the handler, as an error frame.
            try:
                req = ws_request_adapter.validate_json(text)
            except ValidationError as exc:
                logger.warning("ignoring malformed request from control plane: %s", exc)
                continue
            # One task per request so a long build never blocks other calls.
            task = asyncio.create_task(_handle(ws, runtime, transfers, req))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        transfers.abort_all()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def _handle(ws: ClientConnection, runtime: DockerRuntime, transfers: TransferStore, req: Any) -> None:
    try:
        if req.op == "provision":
            r = ProvisionRequest.model_validate(req.args)
            await _pump(ws, req.id, lambda: runtime.provision(r.ree_id, r.image))
        elif req.op == "reprovision":
            rr = ReprovisionRequest.model_validate(req.args)
            await _pump(ws, req.id, lambda: runtime.reprovision(rr.ree_id, rr.location, rr.image))
        elif req.op == "exec_action":
            ea = ExecActionRequest.model_validate(req.args)
            await _pump(ws, req.id, lambda: runtime.exec_action(ea.container_name, ea.cmd_json, ea.run_id, ea.env))
        elif req.op == "is_running":
            ir = IsRunningRequest.model_validate(req.args)
            running = await asyncio.to_thread(runtime.is_running, ir.container_name)
            await _send(ws, req.id, RunningFrame(running=running))
        elif req.op == "exec_query":
            eq = ExecQueryRequest.model_validate(req.args)
            data = await asyncio.to_thread(runtime.exec_query, eq.container_name, eq.argv, eq.timeout)
            # Stream the result in bounded chunks: a sealed archive can be far
            # larger than the transport's receive cap (uvicorn: 16 MiB), and one
            # oversized frame kills the whole multiplexed connection.
            for offset in range(0, len(data), COPY_CHUNK_BYTES):
                chunk = data[offset : offset + COPY_CHUNK_BYTES]
                await _send(ws, req.id, BytesChunkFrame(data_b64=base64.b64encode(chunk).decode()))
            await _send(ws, req.id, DoneFrame())
        elif req.op == "exec_simple":
            es = ExecSimpleRequest.model_validate(req.args)
            await asyncio.to_thread(runtime.exec_simple, es.container_name, es.argv, es.timeout)
            await _send(ws, req.id, DoneFrame())
        elif req.op == "copy_open":
            co = CopyOpenRequest.model_validate(req.args)
            transfer_id = await asyncio.to_thread(transfers.open, co.container_name, co.container_path)
            await _send(ws, req.id, TransferFrame(transfer_id=transfer_id))
        elif req.op == "copy_chunk":
            cc = CopyChunkRequest.model_validate(req.args)
            await asyncio.to_thread(transfers.write, cc.transfer_id, base64.b64decode(cc.data_b64))
            await _send(ws, req.id, DoneFrame())
        elif req.op == "copy_close":
            cl = CopyCloseRequest.model_validate(req.args)
            await asyncio.to_thread(transfers.deliver, cl.transfer_id, runtime.copy_in)
            await _send(ws, req.id, DoneFrame())
        elif req.op == "copy_abort":
            ca = CopyAbortRequest.model_validate(req.args)
            await asyncio.to_thread(transfers.abort, ca.transfer_id)
            await _send(ws, req.id, DoneFrame())
        elif req.op == "remove":
            rm = RemoveRequest.model_validate(req.args)
            await asyncio.to_thread(runtime.remove, rm.ree_id, rm.location)
            await _send(ws, req.id, DoneFrame())
        else:
            await _send(ws, req.id, ErrorFrame(detail=f"unknown op {req.op!r}"))
    except WorkbenchGone as exc:
        await _send(ws, req.id, UnavailableFrame(detail=str(exc)))
    except Exception as exc:  # noqa: BLE001 — any handler failure becomes an error frame
        await _send(ws, req.id, ErrorFrame(detail=str(exc)))


# ================================================
# Sync-to-async streaming bridge
# ================================================


async def _pump(ws: ClientConnection, req_id: str, gen_factory: Callable[[], Iterator[AgentFrame]]) -> None:
    """Run a sync frame generator in a thread, forwarding each frame as it arrives."""
    loop = asyncio.get_running_loop()
    q: asyncio.Queue[Any] = asyncio.Queue()

    def produce() -> None:
        try:
            for frame in gen_factory():
                loop.call_soon_threadsafe(q.put_nowait, frame)
        except WorkbenchGone as exc:
            loop.call_soon_threadsafe(q.put_nowait, UnavailableFrame(detail=str(exc)))
        except Exception as exc:  # noqa: BLE001 — surface any failure as a terminal frame
            loop.call_soon_threadsafe(q.put_nowait, ErrorFrame(detail=str(exc)))
        finally:
            loop.call_soon_threadsafe(q.put_nowait, _STREAM_END)

    threading.Thread(target=produce, daemon=True).start()
    while True:
        frame = await q.get()
        if frame is _STREAM_END:
            return
        await _send(ws, req_id, frame)


async def _send(ws: ClientConnection, req_id: str, frame: AgentFrame) -> None:
    await ws.send(WsMessage(id=req_id, frame=frame).model_dump_json())
