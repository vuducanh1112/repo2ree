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

from repo2ree_protocol.frames import AcceptedFrame, BusyFrame, DoneFrame, ErrorFrame, Frame, ResultFrame, UnknownFrame
from repo2ree_protocol.workbench import (
    CancelRunRequest,
    DeleteReeRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    ExecUploadRequest,
    FetchFileRequest,
    FollowRunRequest,
    ListJournalsRequest,
    ReadJournalRequest,
    StartRunRequest,
    WorkbenchRequest,
)
from repo2ree_workbench.executions import ReeBusyError, UnknownExecutionError
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.uploads import download_file, transfer_url, upload_file


class CallerGoneError(ConnectionError):
    """A frame could not be sent: the connection the request came on is gone."""


SendFrame = Callable[[Frame], Awaitable[None]]
PumpBytes = Callable[[Callable[[], Iterator[bytes]]], Awaitable[None]]


async def dispatch_workbench_request(
    req: WorkbenchRequest,
    service: WorkbenchService,
    *,
    send: SendFrame,
    pump_bytes: PumpBytes,
    record_received: Callable[[int], None],
    api_ws_url: str = "",
) -> None:
    """Run one execution request after transport parsing and correlation.

    ``api_ws_url`` is the address this workbench dialed; an upload goes to the same place."""
    if isinstance(req, StartRunRequest):
        # It waits for one of the workbench's slots; a cancel while it waits ends the wait, and nothing starts.
        try:
            await service.start_run(req.cmd_json, req.run_id, req.env, req.context, ree_id=req.ree_id, wait=req.wait)
        except ReeBusyError as exc:
            await send(BusyFrame(detail=str(exc)))
            return
        await send(AcceptedFrame())
    elif isinstance(req, FollowRunRequest):
        await _follow(service, req, send)
    elif isinstance(req, CancelRunRequest):
        service.cancel_run(req.run_id, ree_id=req.ree_id, record=req.record)
        await send(DoneFrame())
    elif isinstance(req, ListJournalsRequest):
        await pump_bytes(lambda: iter([service.list_journals().model_dump_json().encode()]))
    elif isinstance(req, ReadJournalRequest):
        await pump_bytes(lambda: service.read_journal(req.journal_id, req.after))
    elif isinstance(req, DeleteReeRequest):
        await asyncio.to_thread(service.delete_ree, req.ree_id)
        await send(DoneFrame())
    elif isinstance(req, ExecQueryRequest):
        await pump_bytes(lambda: service.exec_query_stream(req.argv, req.timeout, ree_id=req.ree_id))
    elif isinstance(req, ExecUploadRequest):
        url = transfer_url(api_ws_url, req.transfer_path)
        await asyncio.to_thread(_upload_query, service, req, url)
        await send(DoneFrame())
    elif isinstance(req, ExecSimpleRequest):
        service.exec_simple(req.argv, req.timeout, ree_id=req.ree_id)
        await send(DoneFrame())
    elif isinstance(req, FetchFileRequest):
        url = transfer_url(api_ws_url, req.transfer_path)
        record_received(await asyncio.to_thread(_fetch_into_bench, service, req, url))
        await send(DoneFrame())
    else:
        await send(ErrorFrame(detail=f"unhandled op {req.op!r}"))


async def _follow(service: WorkbenchService, req: FollowRunRequest, send: SendFrame) -> None:
    """Stream the command's log until it ended, then how; its caller leaving ends only the follow."""
    try:
        follower = await asyncio.to_thread(service.follow_run, req.ree_id, req.attempt_id, req.after)
    except UnknownExecutionError as exc:
        await send(UnknownFrame(detail=str(exc)))
        return
    while True:
        frames, result = await asyncio.to_thread(follower.read)
        for frame in frames:
            await send(frame)
        if result is not None:
            await send(ResultFrame(result=result))
            return
        if not frames:
            await asyncio.sleep(service.executions.poll)


def _upload_query(service: WorkbenchService, req: ExecUploadRequest, url: str) -> None:
    """Write the query's output to a file in the bench, send it, and leave nothing behind."""
    handle, name = tempfile.mkstemp(prefix="repo2ree-upload-")
    os.close(handle)
    path = Path(name)
    try:
        service.exec_query_to_file(req.argv, path, req.timeout, ree_id=req.ree_id)
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
        service.copy_in(str(path), req.workbench_path, ree_id=req.ree_id)
        return path.stat().st_size
    finally:
        path.unlink(missing_ok=True)
