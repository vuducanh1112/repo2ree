from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import span_sink, store_registry, workbench_connections, workbench_transfers
from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.machine import MachineFacts
from repo2ree_protocol.workbench import WorkbenchHello, workbench_hello_adapter
from repo2ree_ree.instant import format_utc_instant
from repo2ree_supervisor import (
    StoreClaimedError,
    TransferError,
    WorkbenchConnection,
    WorkbenchUnavailableError,
)
from repo2ree_supervisor.sessions import Session
from repo2ree_supervisor.transfers import TRANSFER_PATH_PREFIX

logger = logging.getLogger(__name__)


workbench_ws_router = APIRouter(tags=["fleet"])


@workbench_ws_router.put(TRANSFER_PATH_PREFIX + "{token}", name="receiveWorkbenchTransfer", include_in_schema=False)
async def receive_workbench_transfer(token: str, request: Request) -> Response:
    length = request.headers.get("content-length", "")
    try:
        await workbench_transfers.receive(token, request.stream(), int(length) if length.isdigit() else None)
    except TransferError as exc:
        logger.warning("refused a workbench transfer: %s", exc)
        return Response(status_code=404 if "no such" in str(exc) else 400)
    return Response(status_code=204)


@workbench_ws_router.get(TRANSFER_PATH_PREFIX + "{token}", name="serveWorkbenchTransfer", include_in_schema=False)
async def serve_workbench_transfer(token: str) -> Response:
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
        logger.warning("send to workbench service failed; closing its connection: %s", fut.exception())
        if connection is not None:
            connection.close("send_failed")

    def send_text(text: str) -> None:
        future = asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)
        future.add_done_callback(on_send_done)

    hello = workbench_hello_adapter.validate_json(await websocket.receive_text())
    token, hello = hello.enrollment_token, hello.model_copy(update={"enrollment_token": ""})
    session = Session(hello, registered=store_registry.get(hello.store_id) is not None)
    if not store_registry.authenticate(token, hello.store_id):
        logger.warning("refused workbench %r for store %r: no valid token for it", hello.workbench_id, hello.store_id)
        session.refuse("bad_token")
        await websocket.close(code=1008, reason="invalid store registration")
        return
    connection = WorkbenchConnection(send_text=send_text, hello=hello, span_sink=span_sink, session=session)
    try:
        workbench_connections.register(hello.workbench_id, connection)
    except StoreClaimedError as exc:
        logger.warning("refused workbench %r: %s", hello.workbench_id, exc)
        session.refuse("store_claimed")
        await websocket.close(code=1008, reason="store already served")
        return
    session.connect()
    close_code: int | None = None
    try:
        while True:
            connection.on_message(await websocket.receive_text())
    except WebSocketDisconnect as exc:
        close_code = exc.code
    finally:
        connection.close("closed", close_code)
        workbench_connections.unregister(hello.workbench_id, connection)


workbenches_router = APIRouter(tags=["fleet"])


class WorkbenchSummary(BaseModel):
    workbench_id: str
    store_id: str
    hostname: str
    version: str
    connected_at: str
    status: str = "connected"


class WorkbenchList(BaseModel):
    workbenches: list[WorkbenchSummary]


class StoreSummary(BaseModel):
    store_id: str
    label: str
    connected: bool
    workbench_id: str | None = None
    slots: int = 0
    machine: MachineFacts | None = None
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
    stores: list[StoreSummary] = []
    for record in store_registry.all():
        hello = _serving_hello(record.store_id)
        stores.append(
            StoreSummary(
                store_id=record.store_id,
                label=record.label or record.store_id,
                connected=hello is not None,
                workbench_id=hello.workbench_id if hello else None,
                slots=hello.slots if hello else 0,
                machine=hello.machine if hello else None,
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
    except WorkbenchUnavailableError:
        return None
