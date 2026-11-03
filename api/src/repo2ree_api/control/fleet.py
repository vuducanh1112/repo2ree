"""The fleet: where workbenches dial in, who is connected, and what they can run.

``/workbench/connect`` is the WebSocket endpoint a workbench service dials and holds
open; the control plane pushes ``WsRequest`` commands down it and receives
``WsMessage`` response frames. The route owns the async I/O and bridges it to
the synchronous ``WorkbenchConnection`` that ``WsWorkbenchClient`` drives: ``send_text``
schedules a send on the loop, and each inbound message is handed to
``on_message``.

``/api/v1/workbenches`` is the read-only fleet view. A workbench appears there for
exactly as long as it holds its socket; the registry drops it on disconnect, so
presence in the list *is* liveness. ``/api/v1/stores`` lists the stores registered
here, each with the workbench serving it now, if any: the labs REEs are created in.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import span_sink, store_registry, workbench_connections, workbench_transfers
from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.workbench import WorkbenchCapabilities, WorkbenchHello, workbench_hello_adapter
from repo2ree_ree.instant import format_utc_instant
from repo2ree_supervisor import (
    StoreClaimedError,
    TransferError,
    WorkbenchConnection,
    WorkbenchUnavailableError,
)
from repo2ree_supervisor.transfers import TRANSFER_PATH_PREFIX

logger = logging.getLogger(__name__)


# ================================================
# Workbench dial-in socket
# ================================================


workbench_ws_router = APIRouter(tags=["fleet"])


@workbench_ws_router.put(TRANSFER_PATH_PREFIX + "{token}", name="receiveWorkbenchTransfer", include_in_schema=False)
async def receive_workbench_transfer(token: str, request: Request) -> Response:
    """A file a workbench uploads for a request waiting on it (``ExecUploadRequest``).

    Not part of the public API: the token in the path is a single-use credential the
    control plane minted for one request, and nothing else is accepted here.
    """
    length = request.headers.get("content-length", "")
    try:
        await workbench_transfers.receive(token, request.stream(), int(length) if length.isdigit() else None)
    except TransferError as exc:
        logger.warning("refused a workbench transfer: %s", exc)
        return Response(status_code=404 if "no such" in str(exc) else 400)
    return Response(status_code=204)


@workbench_ws_router.get(TRANSFER_PATH_PREFIX + "{token}", name="serveWorkbenchTransfer", include_in_schema=False)
async def serve_workbench_transfer(token: str) -> Response:
    """A file the control plane offered a workbench for a request waiting on it (``FetchFileRequest``).

    Not part of the public API, and served once: the token in the path is a
    single-use credential minted for one request.
    """
    try:
        path = workbench_transfers.serve(token)
    except TransferError as exc:
        logger.warning("refused a workbench transfer: %s", exc)
        return Response(status_code=404)
    return FileResponse(path, media_type="application/octet-stream")


@workbench_ws_router.websocket("/workbench/connect", name="connectWorkbench")
async def workbench_connect(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    connection: WorkbenchConnection | None = None

    def on_send_done(fut: Future[None]) -> None:
        if fut.cancelled() or fut.exception() is None:
            return
        # A failed write means the socket is dying. Close the bridge now so
        # blocked callers get an unavailable error immediately, rather than
        # silently losing their request and waiting out the frame-gap timeout.
        logger.warning("send to workbench service failed; closing its connection: %s", fut.exception())
        if connection is not None:
            connection.close()

    def send_text(text: str) -> None:
        # Called from a worker thread (the synchronous manager); hop back onto
        # the event loop to actually write to the socket.
        future = asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)
        future.add_done_callback(on_send_done)

    # First message is the workbench's hello: identity + self-reported capabilities.
    hello = workbench_hello_adapter.validate_json(await websocket.receive_text())
    # A workbench serves a store, and is admitted by a token minted for that store alone.
    if not store_registry.authenticate(hello.enrollment_token, hello.store_id):
        logger.warning("refused workbench %r for store %r: no valid token for it", hello.workbench_id, hello.store_id)
        await websocket.close(code=1008, reason="invalid store registration")
        return
    # Do not retain credentials on live connection objects.
    hello = hello.model_copy(update={"enrollment_token": ""})
    connection = WorkbenchConnection(send_text=send_text, hello=hello, span_sink=span_sink)
    try:
        workbench_connections.register(hello.workbench_id, connection)
    except StoreClaimedError as exc:
        logger.warning("refused workbench %r: %s", hello.workbench_id, exc)
        await websocket.close(code=1008, reason="store already served")
        return
    try:
        while True:
            connection.on_message(await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        connection.close()
        workbench_connections.unregister(hello.workbench_id, connection)


# ================================================
# Fleet view
# ================================================


workbenches_router = APIRouter(tags=["fleet"])


class WorkbenchSummary(BaseModel):
    workbench_id: str
    # The store it serves.
    store_id: str
    hostname: str
    version: str
    # ISO 8601 UTC; when the workbench dialed in.
    connected_at: str
    status: str = "connected"


class WorkbenchList(BaseModel):
    workbenches: list[WorkbenchSummary]


class StoreSummary(BaseModel):
    store_id: str
    label: str
    # Whether a workbench serves the store now; its REEs are reachable only then.
    connected: bool
    workbench_id: str | None = None
    backend: Literal["host", "container"] | None = None
    # The images a new REE in the store may declare, the first the default; none while it runs
    # scripts on its host, or while no workbench serves it.
    images: list[str] = Field(default_factory=list)
    slots: int = 0
    capabilities: WorkbenchCapabilities | None = None
    build: BuildInfo | None = None


class StoreList(BaseModel):
    stores: list[StoreSummary]


@workbenches_router.get(
    "/api/v1/workbenches",
    operation_id="listWorkbenches",
    response_model=WorkbenchList,
    responses=ERROR_RESPONSES,
)
def list_workbenches() -> WorkbenchList:
    """Every workbench service currently connected to this control plane."""
    workbenches = [
        WorkbenchSummary(
            workbench_id=info.workbench_id,
            store_id=info.store_id,
            hostname=info.hostname,
            version=info.version,
            connected_at=format_utc_instant(datetime.fromtimestamp(info.connected_at, tz=UTC)),
        )
        for info in workbench_connections.list_workbenches()
    ]
    return WorkbenchList(workbenches=workbenches)


@workbenches_router.get(
    "/api/v1/stores",
    operation_id="listStores",
    response_model=StoreList,
    responses=ERROR_RESPONSES,
)
def list_stores() -> StoreList:
    """Every store registered here, and the workbench serving each one now, if any."""
    stores: list[StoreSummary] = []
    for record in store_registry.all():
        hello = _serving_hello(record.store_id)
        stores.append(
            StoreSummary(
                store_id=record.store_id,
                label=record.label or record.store_id,
                connected=hello is not None,
                workbench_id=hello.workbench_id if hello else None,
                backend=hello.backend if hello else None,
                images=list(hello.images) if hello else [],
                slots=hello.slots if hello else 0,
                capabilities=hello.capabilities if hello else None,
                build=hello.build if hello else None,
            )
        )
    return StoreList(stores=stores)


def _serving_hello(store_id: str) -> WorkbenchHello | None:
    workbench_id = workbench_connections.store_workbench(store_id)
    if workbench_id is None:
        return None
    try:
        return workbench_connections.pick(workbench_id).hello
    except WorkbenchUnavailableError:  # It went between the two questions.
        return None
