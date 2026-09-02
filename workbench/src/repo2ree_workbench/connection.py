"""Outbound-only control connection: the workbench dials, and never listens.

After the hello it serves ``WsRequest`` messages arriving on the same socket,
handling each concurrently and tagging its response frames with the request id.

The service beneath is synchronous (blocking subprocess plus generators), so
blocking work runs in a thread and streaming work pumps its generator into the
event loop through a bounded memory stream — see ``_pump``.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.metadata
import logging
import queue
import socket
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from functools import partial
from typing import Literal
from uuid import uuid4

import websockets
from pydantic import BaseModel, ConfigDict, ValidationError
from websockets.asyncio.client import ClientConnection, connect

from repo2ree_protocol.frames import (
    BytesChunkFrame,
    DoneFrame,
    ErrorFrame,
    Frame,
    ResultFrame,
    UnavailableFrame,
)
from repo2ree_protocol.result import Failure
from repo2ree_protocol.substrate import ObservedCapabilities
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    WorkbenchSpanAttrs,
    command_metric_attrs,
    get_meter,
    get_tracer,
    record_command_status,
    record_exit_code,
    record_failure,
    remote_context,
)
from repo2ree_protocol.workbench import (
    CancelRequest,
    CancelRunRequest,
    DrainWorkbenchRequest,
    ExecActionRequest,
    WorkbenchHello,
    WorkbenchRequest,
    WorkbenchWsMessage,
    workbench_ws_request_adapter,
)
from repo2ree_workbench.dispatcher import dispatch_workbench_request
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.transfers import TransferStore

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_connection_attempt_counter = _meter.create_counter(
    "workbench.connection_attempt",
    description="Number of outbound WebSocket connection attempts made by a workbench.",
)
_connection_connected_counter = _meter.create_counter(
    "workbench.connection_connected",
    description="Number of successful outbound WebSocket connections made by a workbench.",
)
_connection_lost_counter = _meter.create_counter(
    "workbench.connection_lost",
    description="Number of workbench WebSocket connections that closed or failed.",
)
_connected_gauge = _meter.create_up_down_counter(
    "workbench.connected",
    description="Whether this workbench process currently has an active control-plane connection.",
)
_invalid_request_counter = _meter.create_counter(
    "workbench.invalid_request",
    description="Number of control-plane requests rejected before dispatch.",
)
_cancel_request_counter = _meter.create_counter(
    "workbench.cancel_request",
    description="Number of transport-level request cancellation messages handled by a workbench.",
)
_request_started_counter = _meter.create_counter(
    "workbench.request_started",
    description="Number of control-plane requests started by operation.",
)
_request_duration = _meter.create_histogram(
    "workbench.request_duration_seconds",
    description="Wall-clock duration of a workbench-service-handled control-plane request.",
    unit="s",
)
_active_requests = _meter.create_up_down_counter(
    "workbench.active_requests",
    description="Number of in-flight control-plane requests currently handled by the workbench.",
)
_frame_sent_counter = _meter.create_counter(
    "workbench.frame_sent",
    description="Number of response frames sent by a workbench.",
)
_bytes_sent_counter = _meter.create_counter(
    "workbench.bytes_sent",
    description="Number of payload bytes sent from the workbench to the control plane.",
    unit="By",
)
_bytes_received_counter = _meter.create_counter(
    "workbench.bytes_received",
    description="Number of payload bytes received from the control plane by the workbench.",
    unit="By",
)


# ================================================
# Connection loop
# ================================================


def _workbench_version() -> str:
    try:
        return importlib.metadata.version("repo2ree-workbench")
    except importlib.metadata.PackageNotFoundError:
        return ""


async def run_workbench(
    api_ws_url: str,
    service: WorkbenchService,
    workbench_id: str,
    *,
    mode: Literal["managed", "external"] = "managed",
    allocation_id: str = "",
    enrollment_token: str = "",
    location_id: str = "",
    profile_id: str = "",
    profile_revision: str = "",
    capabilities: ObservedCapabilities | None = None,
    reconnect_delay: float = 3.0,
) -> None:
    """Dial the control plane and serve requests, reconnecting on drop."""
    hello = WorkbenchHello(
        workbench_id=workbench_id,
        mode=mode,
        allocation_id=allocation_id,
        enrollment_token=enrollment_token,
        hostname=socket.gethostname(),
        version=_workbench_version(),
        location_id=location_id,
        profile_id=profile_id,
        profile_revision=profile_revision,
        capabilities=capabilities or ObservedCapabilities(),
        # Minted once per process: reconnects reuse it, so the control plane can
        # tell this instance reconnecting from another instance claiming its id.
        nonce=uuid4().hex,
    )
    while True:
        connection_attrs = {
            "repo2ree.workbench_id": workbench_id,
            "repo2ree.workbench.substrate": str(hello.capabilities.substrate),
        }
        _connection_attempt_counter.add(1, connection_attrs)
        try:
            with tracer.start_as_current_span("workbench.connection") as span:
                span.set_attribute("repo2ree.workbench_id", workbench_id)
                span.set_attribute("repo2ree.workbench.substrate", str(hello.capabilities.substrate))
                async with connect(api_ws_url) as ws:
                    logger.info("workbench %s connected to %s", workbench_id, api_ws_url)
                    _connection_connected_counter.add(1, connection_attrs)
                    _connected_gauge.add(1, connection_attrs)
                    try:
                        await ws.send(hello.model_dump_json())
                        drained = await _serve(ws, service)
                    finally:
                        _connected_gauge.add(-1, connection_attrs)
                    if drained:
                        return
                span.set_attribute("repo2ree.status", "closed")
        except (OSError, websockets.WebSocketException) as exc:
            _connection_lost_counter.add(1, {**connection_attrs, "repo2ree.status": "lost"})
            logger.warning("workbench connection to %s lost (%s); retrying", api_ws_url, exc)
            await asyncio.sleep(reconnect_delay)


# ================================================
# Request dispatch
# ================================================


class _RequestId(BaseModel):
    """Loose parse of just the correlation id, to answer an invalid request."""

    model_config = ConfigDict(extra="ignore")

    id: str


async def _serve(ws: ClientConnection, service: WorkbenchService) -> bool:
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
                req = workbench_ws_request_adapter.validate_json(text)
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
            if isinstance(req.request, DrainWorkbenchRequest):
                if inflight:
                    await asyncio.gather(*inflight.values(), return_exceptions=True)
                await _send(ws, req.id, DoneFrame())
                return True
            # One task per request so a long build never blocks other calls.
            task = asyncio.create_task(_handle(ws, service, transfers, req.id, req.request, req.traceparent))
            inflight[req.id] = task
            task.add_done_callback(partial(_forget_inflight, inflight, req.id))
    finally:
        transfers.abort_all()
        if inflight:
            await asyncio.gather(*inflight.values(), return_exceptions=True)
    return False


def _forget_inflight(inflight: dict[str, asyncio.Task[None]], req_id: str, _task: asyncio.Task[None]) -> None:
    inflight.pop(req_id, None)


@dataclass
class _RequestOutcome:
    """Terminal facts observed on frames or raised by request dispatch."""

    status: str = "succeeded"
    failure: Failure | None = None
    exit_code: int | None = None
    detail: str = ""

    def observe(self, frame: Frame) -> None:
        if isinstance(frame, ResultFrame):
            self.status = frame.result.status
            self.failure = frame.result.failure
            self.exit_code = frame.result.exit_code
            if frame.result.failure is not None:
                self.detail = frame.result.failure.message
        elif isinstance(frame, UnavailableFrame):
            self.status = "unavailable"
            self.detail = frame.detail
        elif isinstance(frame, ErrorFrame):
            self.status = "failed"
            self.detail = frame.detail


async def _handle(
    ws: ClientConnection,
    service: WorkbenchService,
    transfers: TransferStore,
    req_id: str,
    req: WorkbenchRequest,
    traceparent: str | None = None,
) -> None:
    operation = str(req.op)
    metric_attrs = command_metric_attrs(operation)
    _active_requests.add(1, metric_attrs)
    _request_started_counter.add(1, metric_attrs)
    started_at = time.monotonic()
    outcome = _RequestOutcome()
    # Parent this request under the control plane's dispatching span (carried
    # on the WsRequest) so the workbench's work joins the backend's trace instead
    # of rooting its own. A None context means "current", so an untraced
    # request still nests under workbench.connection as before.
    with tracer.start_as_current_span("workbench.request", context=remote_context(traceparent)) as span:
        CommandSpanAttrs(operation=operation).apply(span)
        span.set_attribute("repo2ree.workbench.request_id", req_id)
        # Workbench identity, wherever the request shape carries it: which
        # container/image/REE this request touched should be queryable on the
        # workbench's own span, not only host-side.
        WorkbenchSpanAttrs().apply(span)

        async def send_frame(frame: Frame) -> None:
            outcome.observe(frame)
            await _send(ws, req_id, frame)

        try:
            if isinstance(req, ExecActionRequest | CancelRunRequest):
                span.set_attribute("repo2ree.run_id", req.run_id)
            await dispatch_workbench_request(
                req,
                service,
                transfers,
                send=send_frame,
                pump=lambda factory: _pump(send_frame, factory),
                pump_bytes=lambda factory: _pump_bytes(send_frame, factory),
                record_received=lambda size: _bytes_received_counter.add(size, metric_attrs),
            )
        except asyncio.CancelledError:
            outcome.status = "canceled"
            raise
        except Exception as exc:  # noqa: BLE001 — any handler failure becomes an error frame
            outcome.status = "failed"
            outcome.detail = str(exc)
            span.record_exception(exc)
            await send_frame(ErrorFrame(detail=str(exc)))
        finally:
            record_exit_code(span, outcome.exit_code)
            record_failure(span, outcome.failure)
            record_command_status(span, outcome.status)
            if outcome.status != "succeeded":
                log = logger.info if outcome.status == "canceled" else logger.warning
                log(
                    "workbench request %s (%s) ended %s%s",
                    req_id,
                    operation,
                    outcome.status,
                    f": {outcome.detail}" if outcome.detail else "",
                )
            _active_requests.add(-1, metric_attrs)
            _request_duration.record(
                time.monotonic() - started_at,
                {**metric_attrs, **command_metric_attrs(operation, status=outcome.status)},
            )


# ================================================
# Sync-to-async streaming bridge
# ================================================


async def _pump(send: Callable[[Frame], Awaitable[None]], gen_factory: Callable[[], Iterator[Frame]]) -> None:
    """Run a sync frame generator in a worker thread, forwarding each frame.

    The memory stream is bounded, so a generator that outruns the socket blocks
    on ``send`` (backpressure) instead of piling frames into memory. The stream
    ends the way streams end: the producer closing its side finishes the
    consumer's ``async for``, and the consumer leaving early (a failed send on
    a dying socket) closes the receive side, so the producer's next ``send``
    raises ``BrokenResourceError`` and the thread stops producing.
    """
    sentinel = object()
    pending: queue.Queue[Frame | object] = queue.Queue(maxsize=2)
    stopped = threading.Event()

    def produce() -> None:
        try:
            for frame in gen_factory():
                while not stopped.is_set():
                    try:
                        pending.put(frame, timeout=0.1)
                        break
                    except queue.Full:
                        continue
        except Exception as exc:  # noqa: BLE001 — surface any failure as a terminal frame
            if not stopped.is_set():
                pending.put(ErrorFrame(detail=str(exc)))
        finally:
            if not stopped.is_set():
                pending.put(sentinel)

    threading.Thread(target=produce, daemon=True).start()
    try:
        while True:
            try:
                item = pending.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0)
                continue
            if item is sentinel:
                return
            await send(item)  # type: ignore[arg-type]
    finally:
        stopped.set()


async def _pump_bytes(send: Callable[[Frame], Awaitable[None]], gen_factory: Callable[[], Iterator[bytes]]) -> None:
    """Run a sync byte generator in a thread, framing chunks for the wire."""

    def frames() -> Iterator[Frame]:
        for chunk in gen_factory():
            _bytes_sent_counter.add(len(chunk))
            yield BytesChunkFrame(data_b64=base64.b64encode(chunk).decode())
        yield DoneFrame()

    await _pump(send, frames)


async def _send(ws: ClientConnection, req_id: str, frame: Frame) -> None:
    _frame_sent_counter.add(1, {"repo2ree.workbench.frame_type": frame.type})
    await ws.send(WorkbenchWsMessage(id=req_id, frame=frame).model_dump_json())
