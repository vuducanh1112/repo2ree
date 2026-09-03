"""The fleet: where workbenches dial in, who is connected, and what they can run.

``/workbench/connect`` is the WebSocket endpoint a workbench service dials and holds
open; the control plane pushes ``WsRequest`` commands down it and receives
``WsMessage`` response frames. The route owns the async I/O and bridges it to
the synchronous ``WorkbenchConnection`` that ``WsWorkbenchClient`` drives: ``send_text``
schedules a send on the loop, and each inbound message is handed to
``on_message``.

``/api/v1/workbenches`` is the read-only fleet view. A workbench appears there for
exactly as long as it holds its socket; the registry drops it on disconnect, so
presence in the list *is* liveness. This is the control-plane surface behind
the GUI's workbench-management pane.

Compute locations and fixed profiles are exposed separately by
``control.compute``. Provider-private images never cross this API boundary.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
from concurrent.futures import Future
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import provider_connections, workbench_connections, workbench_enrollments
from repo2ree_api.settings import service_settings
from repo2ree_core.time_utils import iso_utc
from repo2ree_protocol.provider import provider_hello_adapter
from repo2ree_protocol.workbench import WorkbenchHello, workbench_hello_adapter
from repo2ree_supervisor import ProviderConnection, WorkbenchConnection

logger = logging.getLogger(__name__)


# ================================================
# Workbench dial-in socket
# ================================================


workbench_ws_router = APIRouter(tags=["fleet"])
provider_ws_router = APIRouter(tags=["fleet"])


def _external_refusal(hello: WorkbenchHello, expected: str) -> str | None:
    """Why this directly installed workbench may not register, or None to admit it."""
    if hello.allocation_id:
        return "it presented an allocation id, which only a provider-managed workbench has"
    if not expected:
        return "EXTERNAL_WORKBENCH_TOKEN is unset on this control plane, which disables external workbenches"
    if not hmac.compare_digest(hello.enrollment_token, expected):
        return "its token does not match EXTERNAL_WORKBENCH_TOKEN"
    return None


@provider_ws_router.websocket("/provider/connect", name="connectProvider")
async def provider_connect(websocket: WebSocket) -> None:
    """Accept the Docker provider's capacity-only outbound connection."""
    await websocket.accept()
    loop = asyncio.get_running_loop()
    connection: ProviderConnection | None = None

    def on_send_done(fut: Future[None]) -> None:
        if not fut.cancelled() and fut.exception() is not None and connection is not None:
            connection.close()

    def send_text(text: str) -> None:
        future = asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)
        future.add_done_callback(on_send_done)

    hello = provider_hello_adapter.validate_json(await websocket.receive_text())
    connection = ProviderConnection(send_text=send_text, hello=hello)
    provider_connections.register(hello.provider_id, connection)
    try:
        while True:
            connection.on_message(await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        connection.close()
        provider_connections.unregister(hello.provider_id, connection)


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
    if hello.mode == "managed":
        if not hello.allocation_id:
            logger.warning("refused managed workbench %r: it presented no allocation", hello.workbench_id)
            await websocket.close(code=1008, reason="managed workbench has no allocation")
            return
        try:
            workbench_enrollments.authenticate(hello)
        except ValueError as exc:
            logger.warning("refused managed workbench %r: %s", hello.workbench_id, exc)
            await websocket.close(code=1008, reason="invalid workbench enrollment")
            return
        # Do not retain a consumed credential on the live connection object.
    elif refusal := _external_refusal(hello, service_settings.EXTERNAL_WORKBENCH_TOKEN):
        # The close reason stays generic — the peer is unauthenticated and has no
        # claim on which check it failed — but an operator reading the server log
        # gets the specific cause. Without this the three failures below are one
        # opaque 1008 with nothing on this side at all, which is a long way to
        # debug an unset environment variable.
        logger.warning("refused external workbench %r: %s", hello.workbench_id, refusal)
        await websocket.close(code=1008, reason="invalid external workbench registration")
        return
    # Do not retain credentials on live connection objects.
    hello = hello.model_copy(update={"enrollment_token": ""})
    connection = WorkbenchConnection(send_text=send_text, hello=hello)
    workbench_connections.register(hello.workbench_id, connection)
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
    mode: str
    available: bool
    hostname: str
    version: str
    # The base image the bench runs; blank for an externally managed one.
    image: str
    # ISO 8601 UTC; when the workbench dialed in.
    connected_at: str
    status: str = "connected"


class WorkbenchList(BaseModel):
    workbenches: list[WorkbenchSummary]


class ProviderSummary(BaseModel):
    provider_id: str
    hostname: str
    version: str
    location_id: str
    connected_at: str
    status: str = "connected"


class ProviderList(BaseModel):
    providers: list[ProviderSummary]


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
            mode=info.mode,
            available=info.available,
            hostname=info.hostname,
            version=info.version,
            image=info.image,
            connected_at=iso_utc(datetime.fromtimestamp(info.connected_at, tz=UTC)),
        )
        for info in workbench_connections.list_workbenches()
    ]
    return WorkbenchList(workbenches=workbenches)


@workbenches_router.get(
    "/api/v1/providers",
    operation_id="listProviders",
    response_model=ProviderList,
    responses=ERROR_RESPONSES,
)
def list_providers() -> ProviderList:
    """Docker capacity providers currently connected to this control plane."""
    return ProviderList(
        providers=[
            ProviderSummary(
                provider_id=info.provider_id,
                hostname=info.hostname,
                version=info.version,
                location_id=info.location_id,
                connected_at=iso_utc(datetime.fromtimestamp(info.connected_at, tz=UTC)),
            )
            for info in provider_connections.list_providers()
        ]
    )
