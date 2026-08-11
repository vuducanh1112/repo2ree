"""Translate validated wire requests into workbench-service operations."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable, Iterator

from repo2ree_agent.control.transfers import TransferStore
from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.agent import (
    AgentFrame,
    AgentRequest,
    CancelRunRequest,
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
)

SendFrame = Callable[[AgentFrame], Awaitable[None]]
PumpFrames = Callable[[Callable[[], Iterator[AgentFrame]]], Awaitable[None]]
PumpBytes = Callable[[Callable[[], Iterator[bytes]]], Awaitable[None]]


async def dispatch_request(
    req: AgentRequest,
    service: WorkbenchService,
    transfers: TransferStore,
    *,
    send: SendFrame,
    pump: PumpFrames,
    pump_bytes: PumpBytes,
    record_received: Callable[[int], None],
) -> None:
    """Run one request after transport parsing and correlation."""
    if isinstance(req, ProvisionRequest):
        await pump(lambda: service.provision(req.ree_id, req.spec))
    elif isinstance(req, ReprovisionRequest):
        await pump(lambda: service.reprovision(req.ref, req.spec))
    elif isinstance(req, ExecActionRequest):
        await pump(lambda: service.exec_action(req.ref, req.cmd_json, req.run_id, req.env))
    elif isinstance(req, CancelRunRequest):
        await asyncio.to_thread(service.cancel_run, req.ref, req.run_id)
        await send(DoneFrame())
    elif isinstance(req, IsRunningRequest):
        running = await asyncio.to_thread(service.is_running, req.ref)
        await send(RunningFrame(running=running))
    elif isinstance(req, ExecQueryRequest):
        await pump_bytes(lambda: service.exec_query_stream(req.ref, req.argv, req.timeout))
    elif isinstance(req, ExecSimpleRequest):
        await asyncio.to_thread(service.exec_simple, req.ref, req.argv, req.timeout)
        await send(DoneFrame())
    elif isinstance(req, CopyOpenRequest):
        transfer_id = await asyncio.to_thread(transfers.open, req.ref, req.workbench_path)
        await send(TransferFrame(transfer_id=transfer_id))
    elif isinstance(req, CopyChunkRequest):
        chunk = base64.b64decode(req.data_b64)
        record_received(len(chunk))
        await asyncio.to_thread(transfers.write, req.transfer_id, req.offset, chunk)
        await send(DoneFrame())
    elif isinstance(req, CopyCloseRequest):
        await asyncio.to_thread(transfers.deliver, req.transfer_id, service.copy_in)
        await send(DoneFrame())
    elif isinstance(req, CopyAbortRequest):
        await asyncio.to_thread(transfers.abort, req.transfer_id)
        await send(DoneFrame())
    elif isinstance(req, RemoveRequest):
        await asyncio.to_thread(service.remove, req.ref)
        await send(DoneFrame())
    else:
        await send(ErrorFrame(detail=f"unhandled op {req.op!r}"))
