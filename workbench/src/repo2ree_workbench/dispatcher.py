"""Translate validated execution requests into workbench-service operations.

``CancelRequest`` is deliberately absent: it is a transport concern (stop the
in-flight request with that id), so the connection loop that owns the in-flight
table handles it before dispatch ever sees the message.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable, Iterator

from repo2ree_protocol.frames import DoneFrame, ErrorFrame, Frame, TransferFrame
from repo2ree_protocol.workbench import (
    AssignAllocationRequest,
    CancelRunRequest,
    CopyAbortRequest,
    CopyChunkRequest,
    CopyCloseRequest,
    CopyOpenRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    WorkbenchRequest,
)
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.transfers import TransferStore

SendFrame = Callable[[Frame], Awaitable[None]]
PumpFrames = Callable[[Callable[[], Iterator[Frame]]], Awaitable[None]]
PumpBytes = Callable[[Callable[[], Iterator[bytes]]], Awaitable[None]]


async def dispatch_workbench_request(
    req: WorkbenchRequest,
    service: WorkbenchService,
    transfers: TransferStore,
    *,
    send: SendFrame,
    pump: PumpFrames,
    pump_bytes: PumpBytes,
    record_received: Callable[[int], None],
) -> None:
    """Run one execution request after transport parsing and correlation."""
    if isinstance(req, AssignAllocationRequest):
        service.assign(req.allocation)
        await send(DoneFrame())
    elif isinstance(req, ExecActionRequest):
        await pump(lambda: service.exec_action(req.cmd_json, req.run_id, req.env))
    elif isinstance(req, CancelRunRequest):
        service.cancel_run(req.run_id)
        await send(DoneFrame())
    elif isinstance(req, ExecQueryRequest):
        await pump_bytes(lambda: service.exec_query_stream(req.argv, req.timeout))
    elif isinstance(req, ExecSimpleRequest):
        service.exec_simple(req.argv, req.timeout)
        await send(DoneFrame())
    elif isinstance(req, CopyOpenRequest):
        transfer_id = transfers.open(req.workbench_path)
        await send(TransferFrame(transfer_id=transfer_id))
    elif isinstance(req, CopyChunkRequest):
        chunk = base64.b64decode(req.data_b64)
        record_received(len(chunk))
        transfers.write(req.transfer_id, req.offset, chunk)
        await send(DoneFrame())
    elif isinstance(req, CopyCloseRequest):
        transfers.deliver(req.transfer_id, service.copy_in)
        await send(DoneFrame())
    elif isinstance(req, CopyAbortRequest):
        transfers.abort(req.transfer_id)
        await send(DoneFrame())
    else:
        await send(ErrorFrame(detail=f"unhandled op {req.op!r}"))
