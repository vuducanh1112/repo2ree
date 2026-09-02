"""Outbound capacity connection for the Docker provider process."""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import socket
from collections.abc import Awaitable, Callable, Iterator
from functools import partial
from uuid import uuid4

import anyio
import anyio.from_thread
import anyio.to_thread
import websockets
from pydantic import BaseModel, ConfigDict, ValidationError
from websockets.asyncio.client import ClientConnection, connect

from repo2ree_protocol.frames import DoneFrame, ErrorFrame, Frame, RunningFrame
from repo2ree_protocol.provider import (
    IsRunningRequest,
    ProviderCancelRequest,
    ProviderHello,
    ProviderRequest,
    ProviderWsMessage,
    ProvisionRequest,
    RemoveRequest,
    provider_ws_request_adapter,
)
from repo2ree_provider_docker.provisioner import ProvisionerService

logger = logging.getLogger(__name__)


class _RequestId(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str


def _provider_version() -> str:
    try:
        return importlib.metadata.version("repo2ree-provider-docker")
    except importlib.metadata.PackageNotFoundError:
        return ""


async def run_provider(
    api_ws_url: str,
    provisioner: ProvisionerService,
    provider_id: str,
    *,
    docker_mode: str = "",
    reconnect_delay: float = 3.0,
) -> None:
    hello = ProviderHello(
        provider_id=provider_id,
        hostname=socket.gethostname(),
        version=_provider_version(),
        docker_mode=docker_mode,
        nonce=uuid4().hex,
    )
    while True:
        try:
            async with connect(api_ws_url) as ws:
                logger.info("docker provider %s connected to %s", provider_id, api_ws_url)
                await ws.send(hello.model_dump_json())
                await _serve(ws, provisioner)
        except (OSError, websockets.WebSocketException) as exc:
            logger.warning("docker provider connection to %s lost (%s); retrying", api_ws_url, exc)
            await asyncio.sleep(reconnect_delay)


async def _serve(ws: ClientConnection, provisioner: ProvisionerService) -> None:
    inflight: dict[str, asyncio.Task[None]] = {}
    try:
        async for message in ws:
            text = message if isinstance(message, str) else message.decode()
            try:
                envelope = provider_ws_request_adapter.validate_json(text)
            except ValidationError as exc:
                logger.warning("invalid provider request: %s", exc)
                try:
                    req_id = _RequestId.model_validate_json(text).id
                except ValidationError:
                    continue
                await _send(ws, req_id, ErrorFrame(detail=f"invalid request: {exc}"))
                continue
            if isinstance(envelope.request, ProviderCancelRequest):
                target = inflight.get(envelope.request.request_id)
                if target is not None:
                    target.cancel()
                await _send(ws, envelope.id, DoneFrame())
                continue
            task = asyncio.create_task(_handle(ws, provisioner, envelope.id, envelope.request))
            inflight[envelope.id] = task
            task.add_done_callback(partial(_forget, inflight, envelope.id))
    finally:
        if inflight:
            await asyncio.gather(*inflight.values(), return_exceptions=True)


def _forget(inflight: dict[str, asyncio.Task[None]], req_id: str, _task: asyncio.Task[None]) -> None:
    inflight.pop(req_id, None)


async def _handle(
    ws: ClientConnection,
    provisioner: ProvisionerService,
    req_id: str,
    request: ProviderRequest,
) -> None:
    async def send(frame: Frame) -> None:
        await _send(ws, req_id, frame)

    try:
        if isinstance(request, ProvisionRequest):
            await _pump(
                send,
                lambda: provisioner.provision(
                    request.allocation_id,
                    request.workbench_id,
                    request.enrollment_token,
                    request.ree_id,
                    request.spec,
                ),
            )
        elif isinstance(request, IsRunningRequest):
            running = await asyncio.to_thread(provisioner.is_running, request.ref)
            await send(RunningFrame(running=running))
        elif isinstance(request, RemoveRequest):
            await asyncio.to_thread(provisioner.remove, request.ref)
            await send(DoneFrame())
        else:
            raise ValueError("provider cancellation is handled by the transport")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - provider failures become terminal frames
        logger.warning("provider request %s failed: %s", req_id, exc)
        await send(ErrorFrame(detail=str(exc)))


async def _pump(send: Callable[[Frame], Awaitable[None]], factory: Callable[[], Iterator[Frame]]) -> None:
    """Run a sync frame generator in a worker thread, forwarding each frame.

    The producer's own failures become terminal frames *here*, not by escaping
    to ``_handle``: the thread is started with ``abandon_on_cancel`` so a cancel
    need not wait on a blocked Docker call, and an abandoned thread's exception
    is discarded rather than re-raised. A backend that raised without a frame
    would otherwise strand the control plane until its frame-gap timeout, with
    an allocation half-created on this host.
    """
    send_stream, receive_stream = anyio.create_memory_object_stream[Frame](max_buffer_size=2)

    def produce() -> None:
        try:
            with send_stream:
                try:
                    for frame in factory():
                        anyio.from_thread.run(send_stream.send, frame)
                except Exception as exc:  # noqa: BLE001 - surface any failure as a terminal frame
                    logger.warning("provider capacity operation failed: %s", exc)
                    anyio.from_thread.run(send_stream.send, ErrorFrame(detail=str(exc)))
        except (anyio.BrokenResourceError, anyio.ClosedResourceError):
            pass

    async with anyio.create_task_group() as group:
        group.start_soon(partial(anyio.to_thread.run_sync, produce, abandon_on_cancel=True))
        try:
            with receive_stream:
                async for frame in receive_stream:
                    await send(frame)
        finally:
            group.cancel_scope.cancel()


async def _send(ws: ClientConnection, req_id: str, frame: Frame) -> None:
    await ws.send(ProviderWsMessage(id=req_id, frame=frame).model_dump_json())
