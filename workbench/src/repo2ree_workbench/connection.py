from __future__ import annotations

import asyncio
import base64
import contextvars
import logging
import queue
import socket
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from functools import partial
from uuid import uuid4

import websockets
from pydantic import BaseModel, ConfigDict, ValidationError
from websockets.asyncio.client import ClientConnection, connect

from repo2ree_protocol.build import BuildInfo, current_build
from repo2ree_protocol.frames import (
    BytesChunkFrame,
    DoneFrame,
    ErrorFrame,
    Frame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
)
from repo2ree_protocol.machine import MachineFacts
from repo2ree_protocol.result import Failure
from repo2ree_protocol.workbench import (
    CancelRequest,
    CancelRunRequest,
    FollowRunRequest,
    StartRunRequest,
    WorkbenchHello,
    WorkbenchRequest,
    WorkbenchWsMessage,
    workbench_ws_request_adapter,
)
from repo2ree_telemetry.bootstrap import get_meter, get_tracer
from repo2ree_telemetry.spans import (
    CommandSpanAttrs,
    WorkbenchSpanAttrs,
    command_metric_attrs,
    record_command_status,
    record_exit_code,
    record_failure,
    record_result_boundary,
    remote_context,
)
from repo2ree_workbench.dispatcher import CallerGoneError, dispatch_workbench_request
from repo2ree_workbench.service import WorkbenchService

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

PING_INTERVAL = 20.0
PING_TIMEOUT = 20.0
OPEN_TIMEOUT = 10.0
CLOSE_TIMEOUT = 10.0
RECONNECT_DELAY = 3.0
LONGEST_RECONNECT = PING_INTERVAL + PING_TIMEOUT + CLOSE_TIMEOUT + RECONNECT_DELAY + OPEN_TIMEOUT

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


class SpanRelay:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._target: tuple[asyncio.AbstractEventLoop, ClientConnection] | None = None

    def bind(self, loop: asyncio.AbstractEventLoop, ws: ClientConnection) -> None:
        with self._lock:
            self._target = (loop, ws)

    def unbind(self) -> None:
        with self._lock:
            self._target = None

    def send(self, payload: str) -> bool:
        with self._lock:
            target = self._target
        if target is None:
            return False
        loop, ws = target
        message = WorkbenchWsMessage(id=None, frame=SpanFrame(payload=payload)).model_dump_json()
        asyncio.run_coroutine_threadsafe(ws.send(message), loop)
        return True


async def run_workbench(
    api_ws_url: str,
    service: WorkbenchService,
    workbench_id: str,
    *,
    enrollment_token: str = "",
    reconnect_delay: float = RECONNECT_DELAY,
    span_relay: SpanRelay | None = None,
    build: BuildInfo | None = None,
    executor_build: BuildInfo | None = None,
    machine: MachineFacts | None = None,
) -> None:
    component_build = build or current_build("repo2ree-workbench")
    hello = WorkbenchHello(
        workbench_id=workbench_id,
        enrollment_token=enrollment_token,
        hostname=socket.gethostname(),
        version=component_build.version,
        build=component_build,
        executor_build=executor_build or BuildInfo(),
        store_id=service.store_id,
        slots=service.slots,
        machine=machine or MachineFacts(),
        nonce=uuid4().hex,
    )
    while True:
        connection_attrs = {"repo2ree.workbench_id": workbench_id, "repo2ree.store_id": hello.store_id}
        _connection_attempt_counter.add(1, connection_attrs)
        try:
            async with AsyncExitStack() as stack:
                with tracer.start_as_current_span("workbench.dial") as span:
                    span.set_attribute("repo2ree.workbench_id", workbench_id)
                    span.set_attribute("repo2ree.store_id", hello.store_id)
                    ws = await stack.enter_async_context(
                        connect(
                            api_ws_url,
                            ping_interval=PING_INTERVAL,
                            ping_timeout=PING_TIMEOUT,
                            open_timeout=OPEN_TIMEOUT,
                            close_timeout=CLOSE_TIMEOUT,
                        )
                    )
                    logger.info("workbench %s connected to %s", workbench_id, api_ws_url)
                    _connection_connected_counter.add(1, connection_attrs)
                    _connected_gauge.add(1, connection_attrs)
                    await ws.send(hello.model_dump_json())
                if span_relay is not None:
                    span_relay.bind(asyncio.get_running_loop(), ws)
                try:
                    await _serve(ws, service, api_ws_url)
                finally:
                    if span_relay is not None:
                        span_relay.unbind()
                    _connected_gauge.add(-1, connection_attrs)
        except (OSError, websockets.WebSocketException) as exc:
            _connection_lost_counter.add(1, {**connection_attrs, "repo2ree.status": "lost"})
            logger.warning("workbench connection to %s lost (%s); retrying", api_ws_url, exc)
            await asyncio.sleep(reconnect_delay)


class _RequestId(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str


async def _serve(ws: ClientConnection, service: WorkbenchService, api_ws_url: str = "") -> None:
    inflight: dict[str, asyncio.Task[None]] = {}
    try:
        async for message in ws:
            text = message if isinstance(message, str) else message.decode()
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
            if isinstance(req.request, CancelRequest):
                _cancel_request_counter.add(1)
                target = inflight.get(req.request.request_id)
                if target is not None:
                    target.cancel()
                await _send(ws, req.id, DoneFrame())
                continue
            task = asyncio.create_task(_handle(ws, service, req.id, req.request, req.traceparent, api_ws_url))
            inflight[req.id] = task
            task.add_done_callback(partial(_forget_inflight, inflight, req.id))
    finally:
        for task in inflight.values():
            task.cancel()
        if inflight:
            await asyncio.gather(*inflight.values(), return_exceptions=True)


def _forget_inflight(inflight: dict[str, asyncio.Task[None]], req_id: str, _task: asyncio.Task[None]) -> None:
    inflight.pop(req_id, None)


@dataclass
class _RequestOutcome:
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
    req_id: str,
    req: WorkbenchRequest,
    traceparent: str | None = None,
    api_ws_url: str = "",
) -> None:
    operation = str(req.op)
    metric_attrs = command_metric_attrs(operation)
    _active_requests.add(1, metric_attrs)
    _request_started_counter.add(1, metric_attrs)
    started_at = time.monotonic()
    outcome = _RequestOutcome()
    with tracer.start_as_current_span("workbench.request", context=remote_context(traceparent)) as span:
        CommandSpanAttrs(operation=operation).apply(span)
        span.set_attribute("repo2ree.workbench.request_id", req_id)
        WorkbenchSpanAttrs().apply(span)

        async def send_frame(frame: Frame) -> None:
            outcome.observe(frame)
            if isinstance(frame, ResultFrame):
                record_result_boundary(span, "workbench.received", frame.result)
            try:
                await _send(ws, req_id, frame)
            except websockets.ConnectionClosed as exc:
                raise CallerGoneError(str(exc)) from exc
            if isinstance(frame, ResultFrame):
                record_result_boundary(span, "workbench.sent", frame.result)

        try:
            if isinstance(req, StartRunRequest | CancelRunRequest):
                span.set_attribute("repo2ree.run_id", req.run_id)
            if isinstance(req, FollowRunRequest):
                span.set_attribute("repo2ree.attempt_id", req.attempt_id)
            if isinstance(req, StartRunRequest):
                CommandSpanAttrs(operation=operation, run_id=req.run_id, execution=req.context).apply(span)
            await dispatch_workbench_request(
                req,
                service,
                send=send_frame,
                pump_bytes=lambda factory: _pump_bytes(send_frame, factory),
                record_received=lambda size: _bytes_received_counter.add(size, metric_attrs),
                api_ws_url=api_ws_url,
            )
        except asyncio.CancelledError:
            outcome.status = "canceled"
            raise
        except CallerGoneError as exc:
            outcome.status = "canceled"
            outcome.detail = str(exc)
        except Exception as exc:  # noqa: BLE001
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


async def _pump(send: Callable[[Frame], Awaitable[None]], gen_factory: Callable[[], Iterator[Frame]]) -> None:
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
        except Exception as exc:  # noqa: BLE001
            if not stopped.is_set():
                pending.put(ErrorFrame(detail=str(exc)))
        finally:
            if not stopped.is_set():
                pending.put(sentinel)

    worker_context = contextvars.copy_context()
    threading.Thread(target=worker_context.run, args=(produce,), daemon=True).start()
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
    def frames() -> Iterator[Frame]:
        for chunk in gen_factory():
            _bytes_sent_counter.add(len(chunk))
            yield BytesChunkFrame(data_b64=base64.b64encode(chunk).decode())
        yield DoneFrame()

    await _pump(send, frames)


async def _send(ws: ClientConnection, req_id: str, frame: Frame) -> None:
    _frame_sent_counter.add(1, {"repo2ree.workbench.frame_type": frame.type})
    await ws.send(WorkbenchWsMessage(id=req_id, frame=frame).model_dump_json())
