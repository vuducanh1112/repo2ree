"""Translate validated execution requests into workbench-service operations.

``CancelRequest`` is deliberately absent: it is a transport concern (stop the
in-flight request with that id), so the connection loop that owns the in-flight
table handles it before dispatch ever sees the message.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

from repo2ree_protocol.frames import DoneFrame, ErrorFrame, Frame
from repo2ree_protocol.workbench import (
    AssignAllocationRequest,
    CancelRunRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    ExecUploadRequest,
    FetchFileRequest,
    WorkbenchRequest,
)
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.uploads import download_file, transfer_url, upload_file

SendFrame = Callable[[Frame], Awaitable[None]]
PumpFrames = Callable[[Callable[[], Iterator[Frame]]], Awaitable[None]]
PumpBytes = Callable[[Callable[[], Iterator[bytes]]], Awaitable[None]]


async def dispatch_workbench_request(
    req: WorkbenchRequest,
    service: WorkbenchService,
    *,
    send: SendFrame,
    pump: PumpFrames,
    pump_bytes: PumpBytes,
    record_received: Callable[[int], None],
    api_ws_url: str = "",
) -> None:
    """Run one execution request after transport parsing and correlation.

    ``api_ws_url`` is the address this workbench dialed; an upload goes to the same place."""
    if isinstance(req, AssignAllocationRequest):
        service.assign(req.allocation)
        await send(DoneFrame())
    elif isinstance(req, ExecActionRequest):
        await pump(lambda: service.exec_action(req.cmd_json, req.run_id, req.env, req.context))
    elif isinstance(req, CancelRunRequest):
        service.cancel_run(req.run_id)
        await send(DoneFrame())
    elif isinstance(req, ExecQueryRequest):
        await pump_bytes(lambda: service.exec_query_stream(req.argv, req.timeout))
    elif isinstance(req, ExecUploadRequest):
        url = transfer_url(api_ws_url, req.transfer_path)
        await asyncio.to_thread(_upload_query, service, req, url)
        await send(DoneFrame())
    elif isinstance(req, ExecSimpleRequest):
        service.exec_simple(req.argv, req.timeout)
        await send(DoneFrame())
    elif isinstance(req, FetchFileRequest):
        url = transfer_url(api_ws_url, req.transfer_path)
        record_received(await asyncio.to_thread(_fetch_into_bench, service, req, url))
        await send(DoneFrame())
    else:
        await send(ErrorFrame(detail=f"unhandled op {req.op!r}"))


def _upload_query(service: WorkbenchService, req: ExecUploadRequest, url: str) -> None:
    """Write the query's output to a file in the bench, send it, and leave nothing behind."""
    handle, name = tempfile.mkstemp(prefix="repo2ree-upload-")
    os.close(handle)
    path = Path(name)
    try:
        service.exec_query_to_file(req.argv, path, req.timeout)
        upload_file(path, url, timeout=req.timeout)
    finally:
        path.unlink(missing_ok=True)


def _fetch_into_bench(service: WorkbenchService, req: FetchFileRequest, url: str) -> int:
    """Fetch the offered file to the serving host, land it in the bench, leave nothing behind; its size."""
    handle, name = tempfile.mkstemp(prefix="repo2ree-fetch-")
    os.close(handle)
    path = Path(name)
    try:
        download_file(url, path, timeout=req.timeout)
        service.copy_in(str(path), req.workbench_path)
        return path.stat().st_size
    finally:
        path.unlink(missing_ok=True)
