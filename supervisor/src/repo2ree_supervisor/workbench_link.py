"""Control-plane side of the workbench-dialed WebSocket transport.

Each workbench dials the API and holds one connection; the API pushes commands down
it. This module is the control-plane half (the workbench half is
``repo2ree_workbench.connection``):

* ``WorkbenchConnection`` bridges the async socket to the *synchronous* manager. It
  is transport-agnostic — the API's WebSocket route feeds it inbound frames via
  ``on_message`` and gives it a ``send_text`` that schedules a send on the event
  loop. A synchronous caller (the manager, running in a worker thread) blocks on
  a per-request queue while the loop pumps frames into it. One socket multiplexes
  many concurrent requests via correlation ids.
* ``WorkbenchConnectionRegistry`` holds the connected workbenches and resolves placement:
  a request may name the specific workbench an REE is pinned to, or fall back to any
  connected workbench.
* ``WsWorkbenchClient`` implements the ``WorkbenchClient`` seam over the picked
  connection, returning frame streams for the streaming verbs and materialised
  values for the request/response ones. Capacity is a separate seam on a
  separate socket (``provider_link``).
"""

from __future__ import annotations

import base64
import logging
import queue
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import (
    COPY_CHUNK_BYTES,
    TERMINAL_FRAME_TYPES,
    BytesChunkFrame,
    DoneFrame,
    Frame,
    SpanFrame,
    TransferFrame,
    UnavailableFrame,
)
from repo2ree_protocol.tracing import SpanSink, current_traceparent
from repo2ree_protocol.workbench import (
    AssignAllocationRequest,
    CancelRequest,
    CancelRunRequest,
    CopyAbortRequest,
    CopyChunkRequest,
    CopyCloseRequest,
    CopyOpenRequest,
    DrainWorkbenchRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    WorkbenchHello,
    WorkbenchRequest,
    WorkbenchWsRequest,
    workbench_ws_message_adapter,
)
from repo2ree_supervisor.client import WorkbenchUnavailableError, raise_for_terminal_error

logger = logging.getLogger(__name__)

# ================================================
# Tuning constants
# ================================================

# Bound on the silence *between* response frames before a request gives up on
# the workbench (see WorkbenchConnection.request). Streaming verbs use this generous
# default — a provision or command can legitimately be quiet for a while between
# progress lines. Request/response verbs pass something much tighter.
DEFAULT_FRAME_GAP_TIMEOUT = 900.0

# For quick request/response ops (is-running, copy bookkeeping, remove): the
# workbench answers these in milliseconds when healthy, so a short bound turns a
# wedged workbench into a fast, visible failure instead of a blocked worker thread.
QUICK_OP_TIMEOUT = 30.0

# Copy chunks in flight before the oldest ack is drained: enough to hide the
# per-chunk round trip on a remote workbench (throughput would otherwise be one
# chunk per RTT) while bounding what queues in the socket's send path.
COPY_IN_WINDOW = 8


# ================================================
# Fleet view
# ================================================


@dataclass(frozen=True)
class WorkbenchInfo:
    """A connected workbench as the control plane sees it: what the workbench reported
    about itself (``hello``) plus when it dialed in. This is what the fleet view
    lists."""

    workbench_id: str
    mode: str
    available: bool
    hostname: str
    version: str
    location_id: str
    image: str
    connected_at: float  # epoch seconds (UTC)


# ================================================
# Connection bridge (async socket ↔ sync callers)
# ================================================


class WorkbenchConnection:
    """One workbench's socket, bridged from async I/O to synchronous callers."""

    def __init__(
        self,
        send_text: Callable[[str], None],
        hello: WorkbenchHello | None = None,
        *,
        span_sink: SpanSink | None = None,
    ):
        # ``send_text`` schedules a send on the event loop and returns at once.
        # ``hello`` is the workbench's self-description, surfaced by the fleet view.
        # ``span_sink`` receives the workbench's *own* spans, which arrive
        # uncorrelated because they answer no request; None discards them.
        self._send_text = send_text
        self.hello = hello
        self._span_sink = span_sink
        self._pending: dict[str, queue.Queue[Frame]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def on_message(self, text: str) -> None:
        """Route an inbound frame to its waiting caller, or to the span sink."""
        message = workbench_ws_message_adapter.validate_json(text)
        if message.id is None:
            # Unsolicited: the workbench relaying its own telemetry, which
            # correlates to no in-flight request. Checked before the pending
            # lookup, which would otherwise drop it as an unknown id.
            if isinstance(message.frame, SpanFrame) and self._span_sink is not None:
                self._span_sink([message.frame.payload])
            return
        with self._lock:
            q = self._pending.get(message.id)
        if q is not None:
            q.put(message.frame)

    def request(
        self, request: WorkbenchRequest, *, frame_gap_timeout: float = DEFAULT_FRAME_GAP_TIMEOUT
    ) -> Iterator[Frame]:
        """Issue a request and yield its response frames until a terminal one.

        Synchronous and blocking: intended to be called from a worker thread
        while the event loop feeds ``on_message``.

        ``frame_gap_timeout`` bounds the wait *between* frames, not the whole
        call — a long provision that streams progress can run indefinitely, but
        a workbench that goes silent (suspended process, hung docker call, dead
        network with the TCP socket still up) raises ``WorkbenchUnavailableError``
        instead of blocking the caller's thread forever.
        """
        yield from self.start(request).frames(frame_gap_timeout=frame_gap_timeout)

    def start(self, request: WorkbenchRequest) -> PendingReply:
        """Send ``request`` without waiting for its reply.

        The reply arrives on the returned handle; issuing several requests
        before draining the first lets a caller pipeline (see ``copy_in``).
        """
        req_id = uuid4().hex
        q: queue.Queue[Frame] = queue.Queue()
        with self._lock:
            if self._closed:
                raise WorkbenchUnavailableError("workbench connection closed")
            self._pending[req_id] = q
        try:
            # exclude_none keeps the wire identical to the pre-traceparent
            # protocol when tracing is off (see WsRequest).
            self._send_text(
                WorkbenchWsRequest(id=req_id, request=request, traceparent=current_traceparent()).model_dump_json(
                    exclude_none=True
                )
            )
        except BaseException:
            self._discard(req_id)
            raise
        return PendingReply(self, req_id, q, request.op)

    def _discard(self, req_id: str) -> None:
        with self._lock:
            self._pending.pop(req_id, None)

    def _cancel(self, req_id: str) -> None:
        """Fire-and-forget: tell the workbench the caller for ``req_id`` is gone,
        so it can stop the work instead of streaming frames to no one."""
        with self._lock:
            if self._closed:
                return
        with suppress(Exception):
            self._send_text(
                WorkbenchWsRequest(id=uuid4().hex, request=CancelRequest(request_id=req_id)).model_dump_json()
            )

    def close(self) -> None:
        """Mark the connection dead and unblock every waiting caller."""
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for q in pending:
            q.put(UnavailableFrame(detail="workbench connection closed"))


class PendingReply:
    """An issued request whose response frames have not been consumed yet."""

    def __init__(self, connection: WorkbenchConnection, req_id: str, q: queue.Queue[Frame], op: str):
        self._connection = connection
        self._req_id = req_id
        self._queue = q
        self._op = op

    def frames(self, *, frame_gap_timeout: float = DEFAULT_FRAME_GAP_TIMEOUT) -> Iterator[Frame]:
        """Yield the response frames until a terminal one (see ``request``).

        Leaving before the terminal frame — an abandoned stream, or the
        frame-gap timeout firing — sends the workbench a best-effort cancel so it
        stops working for a caller that is gone."""
        terminated = False
        try:
            while True:
                try:
                    frame = self._queue.get(timeout=frame_gap_timeout)
                except queue.Empty:
                    raise WorkbenchUnavailableError(
                        f"workbench stopped responding: no frame for {frame_gap_timeout:.0f}s (op {self._op!r})"
                    ) from None
                if frame.type in TERMINAL_FRAME_TYPES:
                    terminated = True
                yield frame
                if terminated:
                    return
        finally:
            self._connection._discard(self._req_id)  # noqa: SLF001 — the reply and its connection are one mechanism split across two classes in this module
            if not terminated:
                self._connection._cancel(self._req_id)  # noqa: SLF001 — same-module collaborator; see above

    def discard(self) -> None:
        """Stop waiting for this reply without consuming it (error-path cleanup
        for pipelined requests that will never be drained)."""
        self._connection._discard(self._req_id)  # noqa: SLF001 — same-module collaborator; see above


# ================================================
# Workbench registry
# ================================================


class WorkbenchConnectionRegistry:
    """Tracks connected workbenches and resolves placement requests to one of them."""

    def __init__(self, is_allocated: Callable[[str], bool] | None = None) -> None:
        self._workbenches: dict[str, WorkbenchConnection] = {}
        self._connected_at: dict[str, float] = {}
        self._is_allocated = is_allocated or (lambda _workbench_id: False)
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)

    def register(self, workbench_id: str, connection: WorkbenchConnection) -> None:
        """Register a connection under ``workbench_id`` (last-writer-wins).

        If the id is already held by a different connection — a reconnecting
        workbench whose old socket still lingers — the old one is displaced and
        closed so its waiters unblock and it can't later evict its successor.
        """
        with self._lock:
            displaced = self._workbenches.get(workbench_id)
            self._workbenches[workbench_id] = connection
            self._connected_at[workbench_id] = time.time()
            self._changed.notify_all()
        if displaced is not None and displaced is not connection:
            self._log_displacement(workbench_id, displaced, connection)
            displaced.close()

    @staticmethod
    def _log_displacement(workbench_id: str, displaced: WorkbenchConnection, connection: WorkbenchConnection) -> None:
        # The hello nonce is minted per workbench *process*: matching nonces mean the
        # same instance reconnected (routine); differing ones mean a second
        # instance claimed the id — the canary for two workbenches misconfigured with
        # one identity, which last-writer-wins would otherwise hide.
        old_nonce = displaced.hello.nonce if displaced.hello else ""
        new_nonce = connection.hello.nonce if connection.hello else ""
        if old_nonce and old_nonce == new_nonce:
            logger.info("workbench %s reconnected; displacing its previous connection", workbench_id)
        else:
            logger.warning(
                "workbench id %r claimed by a different instance (nonce %s -> %s); displacing the old connection — "
                "check for duplicate workbenches sharing an identity",
                workbench_id,
                old_nonce or "<none>",
                new_nonce or "<none>",
            )

    def unregister(self, workbench_id: str, connection: WorkbenchConnection) -> None:
        """Drop ``workbench_id`` only if ``connection`` still owns it.

        A displaced old socket tearing down must not evict the connection that
        replaced it, so removal is guarded on connection identity."""
        with self._lock:
            if self._workbenches.get(workbench_id) is connection:
                self._workbenches.pop(workbench_id, None)
                self._connected_at.pop(workbench_id, None)
                self._changed.notify_all()

    def wait(self, workbench_id: str, timeout: float) -> None:
        with self._changed:
            if not self._changed.wait_for(lambda: workbench_id in self._workbenches, timeout):
                raise WorkbenchUnavailableError(f"workbench {workbench_id!r} did not connect within {timeout:g}s")

    def reserve_external(self, allocation_id: str, workbench_id: str | None = None) -> str:
        """Atomically claim one connected idle external workbench."""
        with self._lock:
            candidates = [workbench_id] if workbench_id else list(self._workbenches)
            for candidate_id in candidates:
                connection = self._workbenches.get(candidate_id or "")
                if connection is None or connection.hello is None:
                    continue
                location_id = connection.hello.location_id or candidate_id
                if (
                    connection.hello.mode != "external"
                    or location_id != workbench_id
                    or self._is_allocated(candidate_id)
                ):
                    continue
                return candidate_id
        requested = f" {workbench_id!r}" if workbench_id else ""
        raise WorkbenchUnavailableError(f"no idle external workbench{requested} is connected")

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None:
        return None

    def pick(self, workbench_id: str | None = None) -> WorkbenchConnection:
        """Resolve a connection. With ``workbench_id`` set, return that specific workbench
        (placement affinity) or raise if it is not connected. Without it, return
        any connected workbench — the unpinned provision-time path."""
        with self._lock:
            return self._workbenches[self._resolve_locked(workbench_id)]

    def resolve(self, workbench_id: str | None = None) -> str:
        """The id twin of ``pick``: resolve a placement request to a concrete
        workbench id. See ``ProviderClient.resolve_workbench`` for why provision pins."""
        with self._lock:
            return self._resolve_locked(workbench_id)

    def _resolve_locked(self, workbench_id: str | None) -> str:
        """Shared resolution for ``pick``/``resolve``; caller holds ``_lock``."""
        if workbench_id:
            if workbench_id not in self._workbenches:
                raise WorkbenchUnavailableError(f"workbench {workbench_id!r} not connected")
            return workbench_id
        for connected_id in self._workbenches:
            return connected_id
        raise WorkbenchUnavailableError("no workbench service connected")

    def list_workbenches(self) -> list[WorkbenchInfo]:
        """Snapshot of every connected workbench, for the control plane's fleet view."""
        with self._lock:
            infos = [
                WorkbenchInfo(
                    workbench_id=workbench_id,
                    mode=conn.hello.mode if conn.hello else "managed",
                    available=(conn.hello.mode == "external" and not self._is_allocated(workbench_id))
                    if conn.hello
                    else False,
                    hostname=conn.hello.hostname if conn.hello else "",
                    version=conn.hello.version if conn.hello else "",
                    location_id=(conn.hello.location_id or workbench_id) if conn.hello else workbench_id,
                    image=conn.hello.image if conn.hello else "",
                    connected_at=self._connected_at.get(workbench_id, 0.0),
                )
                for workbench_id, conn in self._workbenches.items()
            ]
        infos.sort(key=lambda info: (info.hostname, info.workbench_id))
        return infos


# ================================================
# WebSocket client (both seams)
# ================================================


class WsWorkbenchClient:
    """Execution client backed by a resident workbench connection."""

    def __init__(self, registry: WorkbenchConnectionRegistry):
        self._registry = registry

    def resolve_workbench(self, workbench_id: str) -> str:
        return self._registry.resolve(workbench_id)

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        self._registry.wait(workbench_id, timeout)

    def reserve_external(self, allocation_id: str, location_id: str) -> str:
        workbench_id = self._registry.reserve_external(allocation_id, location_id)
        connection = self._registry.pick(workbench_id)
        actual_location = connection.hello.location_id or workbench_id if connection.hello else workbench_id
        if actual_location != location_id:
            self._registry.release_reservation(workbench_id, allocation_id)
            raise WorkbenchUnavailableError(f"compute location {location_id!r} is unavailable")
        return workbench_id

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None:
        self._registry.release_reservation(workbench_id, allocation_id)

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None:
        self._drain_void(
            self._registry.pick(workbench_id).request(
                AssignAllocationRequest(allocation=allocation),
                frame_gap_timeout=QUICK_OP_TIMEOUT,
            )
        )

    def is_connected(self, workbench_id: str) -> bool:
        try:
            self._registry.pick(workbench_id)
        except WorkbenchUnavailableError:
            return False
        return True

    def is_running(self, workbench_id: str) -> bool:
        """Backward-compatible name for connection liveness."""
        return self.is_connected(workbench_id)

    # ------------------------------------------------
    # Streaming — hand the frame stream straight to the manager.
    # ------------------------------------------------

    def exec_action(self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        return self._registry.pick(workbench_id).request(ExecActionRequest(cmd_json=cmd_json, run_id=run_id, env=env))

    def cancel_run(self, workbench_id: str, run_id: str) -> None:
        conn = self._registry.pick(workbench_id)
        self._drain_void(
            conn.request(
                CancelRunRequest(run_id=run_id),
                frame_gap_timeout=QUICK_OP_TIMEOUT,
            )
        )

    def drain(self, workbench_id: str) -> None:
        conn = self._registry.pick(workbench_id)
        self._drain_void(conn.request(DrainWorkbenchRequest(), frame_gap_timeout=DEFAULT_FRAME_GAP_TIMEOUT))

    # ------------------------------------------------
    # Request/response — materialise the terminal frame.
    # ------------------------------------------------

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        conn = self._registry.pick(workbench_id)
        req = ExecSimpleRequest(argv=argv, timeout=timeout)
        # The workbench enforces ``timeout`` on the exec itself; the frame gap only
        # needs to cover it plus transport slack.
        self._drain_void(conn.request(req, frame_gap_timeout=timeout + QUICK_OP_TIMEOUT))

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30) -> bytes:
        return b"".join(self.exec_query_stream(workbench_id, argv, timeout))

    def exec_query_stream(self, workbench_id: str, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        # The result arrives as bounded chunks ending in ``done``; yield each
        # decoded chunk so large archives do not materialise in control-plane RAM.
        conn = self._registry.pick(workbench_id)
        for frame in conn.request(
            ExecQueryRequest(argv=argv, timeout=timeout),
            frame_gap_timeout=timeout + QUICK_OP_TIMEOUT,
        ):
            if isinstance(frame, BytesChunkFrame):
                yield base64.b64decode(frame.data_b64)
            elif isinstance(frame, DoneFrame):
                return
            else:
                raise_for_terminal_error(frame)
        raise RuntimeError("workbench exec_query ended without a result")

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str) -> None:
        # Chunked copy-in over the workbench protocol, read straight from disk.
        # Chunks are pipelined: up to COPY_IN_WINDOW ride the wire before the
        # oldest ack is drained, so throughput is bound by bandwidth, not by one
        # round trip per chunk. Each chunk carries its offset, so the workbench can
        # apply them in whatever order they land.
        # On any failure, tell the workbench to drop its partial temp file.
        conn = self._registry.pick(workbench_id)
        transfer_id = self._open_transfer(conn, workbench_path)
        in_flight: deque[PendingReply] = deque()
        try:
            with Path(source_path).open("rb") as source:
                offset = 0
                while chunk := source.read(COPY_CHUNK_BYTES):
                    in_flight.append(
                        conn.start(
                            CopyChunkRequest(
                                transfer_id=transfer_id,
                                offset=offset,
                                data_b64=base64.b64encode(chunk).decode(),
                            )
                        )
                    )
                    offset += len(chunk)
                    if len(in_flight) >= COPY_IN_WINDOW:
                        self._drain_void(in_flight.popleft().frames(frame_gap_timeout=QUICK_OP_TIMEOUT))
            while in_flight:
                self._drain_void(in_flight.popleft().frames(frame_gap_timeout=QUICK_OP_TIMEOUT))
            # copy_close runs `docker cp` of the assembled file on the workbench;
            # give it more room than the per-chunk acks.
            self._drain_void(conn.request(CopyCloseRequest(transfer_id=transfer_id), frame_gap_timeout=180.0))
        except BaseException:
            while in_flight:
                in_flight.popleft().discard()
            with suppress(Exception):
                self._drain_void(
                    conn.request(CopyAbortRequest(transfer_id=transfer_id), frame_gap_timeout=QUICK_OP_TIMEOUT)
                )
            raise

    def _open_transfer(self, conn: WorkbenchConnection, workbench_path: str) -> str:
        req = CopyOpenRequest(workbench_path=workbench_path)
        for frame in conn.request(req, frame_gap_timeout=QUICK_OP_TIMEOUT):
            if isinstance(frame, TransferFrame):
                return frame.transfer_id
            raise_for_terminal_error(frame)
        raise RuntimeError("workbench copy_open ended without a transfer id")

    def _drain_void(self, frames: Iterator[Frame]) -> None:
        """Consume a stream whose only meaningful outcome is success or error."""
        for frame in frames:
            raise_for_terminal_error(frame)
