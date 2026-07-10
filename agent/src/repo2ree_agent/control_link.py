"""Agent-dialed WebSocket mode (Step 1): outbound-only, no listening port.

The agent dials the control plane, sends a hello, then serves ``WsRequest``
messages that arrive over the same connection — the control plane pushes work
down the agent-initiated socket. Each request is handled concurrently; its
response frames are tagged with the request id and streamed back.

The runtime behind the requests is anything satisfying ``WorkbenchRuntime``
(today: ``DockerRuntime``). Runtimes are synchronous (blocking subprocess +
generators), so blocking work runs in a thread (``asyncio.to_thread``) and
streaming ops pump their sync generator from a worker thread into the event
loop through a bounded anyio memory stream, forwarding each frame as it
arrives.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.metadata
import logging
import socket
import time
from collections.abc import Callable, Iterator
from functools import partial
from uuid import uuid4

import anyio
import anyio.from_thread
import anyio.to_thread
import websockets
from pydantic import BaseModel, ConfigDict, ValidationError
from websockets.asyncio.client import ClientConnection, connect

from repo2ree_agent.docker_runtime import DockerRuntime
from repo2ree_agent.transfers import TransferStore
from repo2ree_agent.workbench_runtime import WorkbenchGone, WorkbenchRuntime
from repo2ree_protocol.agent import (
    AgentFrame,
    AgentHello,
    AgentRequest,
    BytesChunkFrame,
    CancelRequest,
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
    UnavailableFrame,
    WsMessage,
    ws_request_adapter,
)
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    command_metric_attrs,
    get_meter,
    get_tracer,
    record_command_status,
    remote_context,
)

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_connection_attempt_counter = _meter.create_counter(
    "agent.connection_attempt",
    description="Number of outbound WebSocket connection attempts made by an agent.",
)
_connection_connected_counter = _meter.create_counter(
    "agent.connection_connected",
    description="Number of successful outbound WebSocket connections made by an agent.",
)
_connection_lost_counter = _meter.create_counter(
    "agent.connection_lost",
    description="Number of agent WebSocket connections that closed or failed.",
)
_invalid_request_counter = _meter.create_counter(
    "agent.invalid_request",
    description="Number of control-plane requests rejected before dispatch.",
)
_cancel_request_counter = _meter.create_counter(
    "agent.cancel_request",
    description="Number of transport-level request cancellation messages handled by an agent.",
)
_request_started_counter = _meter.create_counter(
    "agent.request_started",
    description="Number of control-plane requests started by operation.",
)
_request_duration = _meter.create_histogram(
    "agent.request_duration_seconds",
    description="Wall-clock duration of an agent-handled control-plane request.",
    unit="s",
)
_active_requests = _meter.create_up_down_counter(
    "agent.active_requests",
    description="Number of in-flight control-plane requests currently handled by the agent.",
)
_frame_sent_counter = _meter.create_counter(
    "agent.frame_sent",
    description="Number of response frames sent by an agent.",
)
_bytes_sent_counter = _meter.create_counter(
    "agent.bytes_sent",
    description="Number of payload bytes sent from the agent to the control plane.",
    unit="By",
)
_bytes_received_counter = _meter.create_counter(
    "agent.bytes_received",
    description="Number of payload bytes received from the control plane by the agent.",
    unit="By",
)


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
    runtime: WorkbenchRuntime = DockerRuntime(docker_mode)
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
        connection_attrs = {
            "repo2ree.agent_id": agent_id,
            "repo2ree.agent.docker_mode": docker_mode,
        }
        _connection_attempt_counter.add(1, connection_attrs)
        try:
            with tracer.start_as_current_span("agent.connection") as span:
                span.set_attribute("repo2ree.agent_id", agent_id)
                span.set_attribute("repo2ree.agent.docker_mode", docker_mode)
                async with connect(api_ws_url) as ws:
                    logger.info("agent %s connected to %s", agent_id, api_ws_url)
                    _connection_connected_counter.add(1, connection_attrs)
                    await ws.send(hello.model_dump_json())
                    await _serve(ws, runtime)
                span.set_attribute("repo2ree.status", "closed")
        except (OSError, websockets.WebSocketException) as exc:
            _connection_lost_counter.add(1, {**connection_attrs, "repo2ree.status": "lost"})
            logger.warning("agent connection to %s lost (%s); retrying", api_ws_url, exc)
            await asyncio.sleep(reconnect_delay)


# ================================================
# Request dispatch
# ================================================


class _RequestId(BaseModel):
    """Loose parse of just the correlation id, to answer an invalid request."""

    model_config = ConfigDict(extra="ignore")

    id: str


async def _serve(ws: ClientConnection, runtime: WorkbenchRuntime) -> None:
    # Chunked copy-in transfers are scoped to this connection; if it drops with
    # any still open, their partial temp files are discarded rather than leaked.
    transfers = TransferStore()
    # Hold a strong reference to every in-flight handler: the event loop only
    # keeps a weak one, so a task dropped here could be garbage-collected
    # mid-request — silently losing its response and hanging the caller. Keyed
    # by request id so a ``cancel`` can find its target.
    inflight: dict[str, asyncio.Task[None]] = {}
    try:
        async for message in ws:
            text = message if isinstance(message, str) else message.decode()
            # An invalid request (say, a version-skewed control plane) must not
            # tear down the socket and abort every in-flight call. If its id is
            # recoverable, fail soft with an error frame so the caller is not
            # left waiting; without an id there is no one to answer — drop it.
            try:
                req = ws_request_adapter.validate_json(text)
            except ValidationError as exc:
                _invalid_request_counter.add(1)
                logger.warning("invalid request from control plane: %s", exc)
                try:
                    req_id = _RequestId.model_validate_json(text).id
                except ValidationError:
                    continue
                await _send(ws, req_id, ErrorFrame(detail=f"invalid request: {exc}"))
                continue
            # Cancels are handled inline, not as tasks: the target's caller is
            # gone, so stop its work. Idempotent — an already-finished (or
            # never-known) target still answers done.
            if isinstance(req.request, CancelRequest):
                _cancel_request_counter.add(1)
                target = inflight.get(req.request.request_id)
                if target is not None:
                    target.cancel()
                await _send(ws, req.id, DoneFrame())
                continue
            # One task per request so a long build never blocks other calls.
            task = asyncio.create_task(_handle(ws, runtime, transfers, req.id, req.request, req.traceparent))
            inflight[req.id] = task
            task.add_done_callback(partial(_forget_inflight, inflight, req.id))
    finally:
        transfers.abort_all()
        if inflight:
            await asyncio.gather(*inflight.values(), return_exceptions=True)


def _forget_inflight(inflight: dict[str, asyncio.Task[None]], req_id: str, _task: asyncio.Task[None]) -> None:
    inflight.pop(req_id, None)


async def _handle(
    ws: ClientConnection,
    runtime: WorkbenchRuntime,
    transfers: TransferStore,
    req_id: str,
    req: AgentRequest,
    traceparent: str | None = None,
) -> None:
    operation = str(req.op)
    metric_attrs = command_metric_attrs(operation)
    _active_requests.add(1, metric_attrs)
    _request_started_counter.add(1, metric_attrs)
    started_at = time.monotonic()
    status = "succeeded"
    # Parent this request under the control plane's dispatching span (carried
    # on the WsRequest) so the agent's work joins the backend's trace instead
    # of rooting its own. A None context means "current", so an untraced
    # request still nests under agent.connection as before.
    with tracer.start_as_current_span("agent.request", context=remote_context(traceparent)) as span:
        CommandSpanAttrs(operation=operation).apply(span)
        span.set_attribute("repo2ree.agent.request_id", req_id)
        try:
            if isinstance(req, ProvisionRequest):
                await _pump(ws, req_id, lambda: runtime.provision(req.ree_id, req.image))
            elif isinstance(req, ReprovisionRequest):
                await _pump(ws, req_id, lambda: runtime.reprovision(req.ree_id, req.location, req.image))
            elif isinstance(req, ExecActionRequest):
                span.set_attribute("repo2ree.run_id", req.run_id)
                await _pump(ws, req_id, lambda: runtime.exec_action(req.location, req.cmd_json, req.run_id, req.env))
            elif isinstance(req, CancelRunRequest):
                span.set_attribute("repo2ree.run_id", req.run_id)
                await asyncio.to_thread(runtime.cancel_run, req.location, req.run_id)
                await _send(ws, req_id, DoneFrame())
            elif isinstance(req, IsRunningRequest):
                running = await asyncio.to_thread(runtime.is_running, req.location)
                await _send(ws, req_id, RunningFrame(running=running))
            elif isinstance(req, ExecQueryRequest):
                await _pump_bytes(ws, req_id, lambda: runtime.exec_query_stream(req.location, req.argv, req.timeout))
            elif isinstance(req, ExecSimpleRequest):
                await asyncio.to_thread(runtime.exec_simple, req.location, req.argv, req.timeout)
                await _send(ws, req_id, DoneFrame())
            elif isinstance(req, CopyOpenRequest):
                transfer_id = await asyncio.to_thread(transfers.open, req.location, req.container_path)
                await _send(ws, req_id, TransferFrame(transfer_id=transfer_id))
            elif isinstance(req, CopyChunkRequest):
                chunk = base64.b64decode(req.data_b64)
                _bytes_received_counter.add(len(chunk), command_metric_attrs(operation))
                await asyncio.to_thread(transfers.write, req.transfer_id, req.offset, chunk)
                await _send(ws, req_id, DoneFrame())
            elif isinstance(req, CopyCloseRequest):
                await asyncio.to_thread(transfers.deliver, req.transfer_id, runtime.copy_in)
                await _send(ws, req_id, DoneFrame())
            elif isinstance(req, CopyAbortRequest):
                await asyncio.to_thread(transfers.abort, req.transfer_id)
                await _send(ws, req_id, DoneFrame())
            elif isinstance(req, RemoveRequest):
                await asyncio.to_thread(runtime.remove, req.ree_id, req.location)
                await _send(ws, req_id, DoneFrame())
            else:
                status = "failed"
                await _send(ws, req_id, ErrorFrame(detail=f"unhandled op {req.op!r}"))
        except WorkbenchGone as exc:
            status = "unavailable"
            await _send(ws, req_id, UnavailableFrame(detail=str(exc)))
        except asyncio.CancelledError:
            status = "canceled"
            raise
        except Exception as exc:  # noqa: BLE001 — any handler failure becomes an error frame
            status = "failed"
            span.record_exception(exc)
            await _send(ws, req_id, ErrorFrame(detail=str(exc)))
        finally:
            record_command_status(span, status)
            _active_requests.add(-1, metric_attrs)
            _request_duration.record(
                time.monotonic() - started_at,
                command_metric_attrs(operation, status=status),
            )


# ================================================
# Sync-to-async streaming bridge
# ================================================


async def _pump(ws: ClientConnection, req_id: str, gen_factory: Callable[[], Iterator[AgentFrame]]) -> None:
    """Run a sync frame generator in a worker thread, forwarding each frame.

    The memory stream is bounded, so a generator that outruns the socket blocks
    on ``send`` (backpressure) instead of piling frames into memory. The stream
    ends the way streams end: the producer closing its side finishes the
    consumer's ``async for``, and the consumer leaving early (a failed send on
    a dying socket) closes the receive side, so the producer's next ``send``
    raises ``BrokenResourceError`` and the thread stops producing.
    """
    send_stream, receive_stream = anyio.create_memory_object_stream[AgentFrame](max_buffer_size=2)

    def produce() -> None:
        try:
            with send_stream:
                try:
                    for frame in gen_factory():
                        anyio.from_thread.run(send_stream.send, frame)
                except WorkbenchGone as exc:
                    anyio.from_thread.run(send_stream.send, UnavailableFrame(detail=str(exc)))
                except Exception as exc:  # noqa: BLE001 — surface any failure as a terminal frame
                    anyio.from_thread.run(send_stream.send, ErrorFrame(detail=str(exc)))
        except (anyio.BrokenResourceError, anyio.ClosedResourceError):
            pass  # the consumer left; there is no one to produce for

    async with anyio.create_task_group() as tg:
        # ``abandon_on_cancel``: the generator may sit in a long docker call;
        # ending the request must not wait for it. The abandoned thread stops
        # at its next send (the closed stream), like any detached producer.
        tg.start_soon(partial(anyio.to_thread.run_sync, produce, abandon_on_cancel=True))
        try:
            with receive_stream:
                async for frame in receive_stream:
                    await _send(ws, req_id, frame)
        finally:
            tg.cancel_scope.cancel()


async def _pump_bytes(ws: ClientConnection, req_id: str, gen_factory: Callable[[], Iterator[bytes]]) -> None:
    """Run a sync byte generator in a thread, framing chunks for the wire."""

    def frames() -> Iterator[AgentFrame]:
        for chunk in gen_factory():
            _bytes_sent_counter.add(len(chunk))
            yield BytesChunkFrame(data_b64=base64.b64encode(chunk).decode())
        yield DoneFrame()

    await _pump(ws, req_id, frames)


async def _send(ws: ClientConnection, req_id: str, frame: AgentFrame) -> None:
    _frame_sent_counter.add(1, {"repo2ree.agent.frame_type": frame.type})
    await ws.send(WsMessage(id=req_id, frame=frame).model_dump_json())
