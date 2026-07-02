"""Control-plane side of the agent-dialed WebSocket transport (Step 1).

The agent dials the API and holds one connection; the API pushes commands down
it. This module is the control-plane half:

* ``AgentConnection`` bridges the async socket to the *synchronous* manager. It
  is transport-agnostic — the API's WebSocket route feeds it inbound frames via
  ``on_message`` and gives it a ``send_text`` that schedules a send on the event
  loop. A synchronous caller (the manager, running in a worker thread) blocks on
  a per-request queue while the loop pumps frames into it. One socket multiplexes
  many concurrent requests via correlation ids.
* ``AgentConnectionRegistry`` holds the connected agents.
* ``WsAgentClient`` is an ``AgentClient`` that drives ops over the picked
  connection, returning frame streams for the streaming verbs and materialised
  values for the request/response ones.

Step 1 scope: a single agent. ``pick()`` returns the one connected agent;
multi-agent placement (recording which agent owns which REE) comes with the
broker step.
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
from uuid import uuid4

from repo2ree_protocol.agent import (
    COPY_CHUNK_BYTES,
    TERMINAL_FRAME_TYPES,
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
    WorkbenchLocation,
    WsRequest,
    ws_message_adapter,
)
from repo2ree_supervisor.client import WorkbenchUnavailableError, raise_for_terminal_error

logger = logging.getLogger(__name__)

# Bound on the silence *between* response frames before a request gives up on
# the agent (see AgentConnection.request). Streaming verbs use this generous
# default — a provision or command can legitimately be quiet for a while between
# progress lines. Request/response verbs pass something much tighter.
DEFAULT_FRAME_GAP_TIMEOUT = 900.0

# For quick request/response ops (is-running, copy bookkeeping, remove): the
# agent answers these in milliseconds when healthy, so a short bound turns a
# wedged agent into a fast, visible failure instead of a blocked worker thread.
QUICK_OP_TIMEOUT = 30.0

# Copy chunks in flight before the oldest ack is drained: enough to hide the
# per-chunk round trip on a remote agent (throughput would otherwise be one
# chunk per RTT) while bounding what queues in the socket's send path.
COPY_IN_WINDOW = 8


@dataclass(frozen=True)
class AgentInfo:
    """A connected agent as the control plane sees it: what the agent reported
    about itself (``hello``) plus when it dialed in. This is what the fleet view
    lists."""

    agent_id: str
    hostname: str
    version: str
    docker_mode: str
    connected_at: float  # epoch seconds (UTC)


class AgentConnection:
    """One agent's socket, bridged from async I/O to synchronous callers."""

    def __init__(self, send_text: Callable[[str], None], hello: AgentHello | None = None):
        # ``send_text`` schedules a send on the event loop and returns at once.
        # ``hello`` is the agent's self-description, surfaced by the fleet view.
        self._send_text = send_text
        self.hello = hello
        self._pending: dict[str, queue.Queue[AgentFrame]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def on_message(self, text: str) -> None:
        """Route an inbound response frame to its waiting caller (async side)."""
        message = ws_message_adapter.validate_json(text)
        with self._lock:
            q = self._pending.get(message.id)
        if q is not None:
            q.put(message.frame)

    def request(
        self, request: AgentRequest, *, frame_gap_timeout: float = DEFAULT_FRAME_GAP_TIMEOUT
    ) -> Iterator[AgentFrame]:
        """Issue a request and yield its response frames until a terminal one.

        Synchronous and blocking: intended to be called from a worker thread
        while the event loop feeds ``on_message``.

        ``frame_gap_timeout`` bounds the wait *between* frames, not the whole
        call — a long provision that streams progress can run indefinitely, but
        an agent that goes silent (suspended process, hung docker call, dead
        network with the TCP socket still up) raises ``WorkbenchUnavailableError``
        instead of blocking the caller's thread forever.
        """
        yield from self.start(request).frames(frame_gap_timeout=frame_gap_timeout)

    def start(self, request: AgentRequest) -> PendingReply:
        """Send ``request`` without waiting for its reply.

        The reply arrives on the returned handle; issuing several requests
        before draining the first lets a caller pipeline (see ``copy_in``).
        """
        req_id = uuid4().hex
        q: queue.Queue[AgentFrame] = queue.Queue()
        with self._lock:
            if self._closed:
                raise WorkbenchUnavailableError("agent connection closed")
            self._pending[req_id] = q
        try:
            self._send_text(WsRequest(id=req_id, request=request).model_dump_json())
        except BaseException:
            self._discard(req_id)
            raise
        return PendingReply(self, req_id, q, request.op)

    def _discard(self, req_id: str) -> None:
        with self._lock:
            self._pending.pop(req_id, None)

    def _cancel(self, req_id: str) -> None:
        """Fire-and-forget: tell the agent the caller for ``req_id`` is gone,
        so it can stop the work instead of streaming frames to no one."""
        with self._lock:
            if self._closed:
                return
        with suppress(Exception):
            self._send_text(WsRequest(id=uuid4().hex, request=CancelRequest(request_id=req_id)).model_dump_json())

    def close(self) -> None:
        """Mark the connection dead and unblock every waiting caller."""
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for q in pending:
            q.put(UnavailableFrame(detail="agent connection closed"))


class PendingReply:
    """An issued request whose response frames have not been consumed yet."""

    def __init__(self, connection: AgentConnection, req_id: str, q: queue.Queue[AgentFrame], op: str):
        self._connection = connection
        self._req_id = req_id
        self._queue = q
        self._op = op

    def frames(self, *, frame_gap_timeout: float = DEFAULT_FRAME_GAP_TIMEOUT) -> Iterator[AgentFrame]:
        """Yield the response frames until a terminal one (see ``request``).

        Leaving before the terminal frame — an abandoned stream, or the
        frame-gap timeout firing — sends the agent a best-effort cancel so it
        stops working for a caller that is gone."""
        terminated = False
        try:
            while True:
                try:
                    frame = self._queue.get(timeout=frame_gap_timeout)
                except queue.Empty:
                    raise WorkbenchUnavailableError(
                        f"agent stopped responding: no frame for {frame_gap_timeout:.0f}s (op {self._op!r})"
                    ) from None
                if frame.type in TERMINAL_FRAME_TYPES:
                    terminated = True
                yield frame
                if terminated:
                    return
        finally:
            self._connection._discard(self._req_id)
            if not terminated:
                self._connection._cancel(self._req_id)

    def discard(self) -> None:
        """Stop waiting for this reply without consuming it (error-path cleanup
        for pipelined requests that will never be drained)."""
        self._connection._discard(self._req_id)


class AgentConnectionRegistry:
    """Tracks connected agents. Step 1: one is expected; ``pick`` returns it."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentConnection] = {}
        self._connected_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def register(self, agent_id: str, connection: AgentConnection) -> None:
        """Register a connection under ``agent_id`` (last-writer-wins).

        If the id is already held by a different connection — a reconnecting
        agent whose old socket still lingers — the old one is displaced and
        closed so its waiters unblock and it can't later evict its successor.
        """
        with self._lock:
            displaced = self._agents.get(agent_id)
            self._agents[agent_id] = connection
            self._connected_at[agent_id] = time.time()
        if displaced is not None and displaced is not connection:
            self._log_displacement(agent_id, displaced, connection)
            displaced.close()

    @staticmethod
    def _log_displacement(agent_id: str, displaced: AgentConnection, connection: AgentConnection) -> None:
        # The hello nonce is minted per agent *process*: matching nonces mean the
        # same instance reconnected (routine); differing ones mean a second
        # instance claimed the id — the canary for two agents misconfigured with
        # one identity, which last-writer-wins would otherwise hide.
        old_nonce = displaced.hello.nonce if displaced.hello else ""
        new_nonce = connection.hello.nonce if connection.hello else ""
        if old_nonce and old_nonce == new_nonce:
            logger.info("agent %s reconnected; displacing its previous connection", agent_id)
        else:
            logger.warning(
                "agent id %r claimed by a different instance (nonce %s -> %s); displacing the old connection — "
                "check for duplicate agents sharing an identity",
                agent_id,
                old_nonce or "<none>",
                new_nonce or "<none>",
            )

    def unregister(self, agent_id: str, connection: AgentConnection) -> None:
        """Drop ``agent_id`` only if ``connection`` still owns it.

        A displaced old socket tearing down must not evict the connection that
        replaced it, so removal is guarded on connection identity."""
        with self._lock:
            if self._agents.get(agent_id) is connection:
                self._agents.pop(agent_id, None)
                self._connected_at.pop(agent_id, None)

    def pick(self, agent_id: str | None = None) -> AgentConnection:
        """Resolve a connection. With ``agent_id`` set, return that specific agent
        (placement affinity) or raise if it is not connected. Without it, return
        any connected agent — the single-agent / legacy path."""
        with self._lock:
            return self._agents[self._resolve_locked(agent_id)]

    def resolve(self, agent_id: str | None = None) -> str:
        """The id twin of ``pick``: resolve a placement request to a concrete
        agent id. See ``AgentClient.resolve_agent`` for why provision pins."""
        with self._lock:
            return self._resolve_locked(agent_id)

    def _resolve_locked(self, agent_id: str | None) -> str:
        """Shared resolution for ``pick``/``resolve``; caller holds ``_lock``."""
        if agent_id:
            if agent_id not in self._agents:
                raise WorkbenchUnavailableError(f"agent {agent_id!r} not connected")
            return agent_id
        for connected_id in self._agents:
            return connected_id
        raise WorkbenchUnavailableError("no workbench agent connected")

    def list_agents(self) -> list[AgentInfo]:
        """Snapshot of every connected agent, for the control plane's fleet view."""
        with self._lock:
            infos = [
                AgentInfo(
                    agent_id=agent_id,
                    hostname=conn.hello.hostname if conn.hello else "",
                    version=conn.hello.version if conn.hello else "",
                    docker_mode=conn.hello.docker_mode if conn.hello else "",
                    connected_at=self._connected_at.get(agent_id, 0.0),
                )
                for agent_id, conn in self._agents.items()
            ]
        infos.sort(key=lambda info: (info.hostname, info.agent_id))
        return infos


class WsAgentClient:
    """An ``AgentClient`` backed by an agent-dialed WebSocket connection."""

    def __init__(self, registry: AgentConnectionRegistry):
        self._registry = registry

    def resolve_agent(self, agent_id: str) -> str:
        return self._registry.resolve(agent_id)

    # ------------------------------------------------
    # Streaming — hand the frame stream straight to the manager.
    # ------------------------------------------------

    def provision(self, agent_id: str, ree_id: str, image: str) -> Iterator[AgentFrame]:
        return self._registry.pick(agent_id).request(ProvisionRequest(ree_id=ree_id, image=image))

    def reprovision(self, agent_id: str, ree_id: str, location: WorkbenchLocation, image: str) -> Iterator[AgentFrame]:
        return self._registry.pick(agent_id).request(ReprovisionRequest(ree_id=ree_id, location=location, image=image))

    def exec_action(
        self, agent_id: str, container_name: str, cmd_json: str, run_id: str, env: dict[str, str]
    ) -> Iterator[AgentFrame]:
        return self._registry.pick(agent_id).request(
            ExecActionRequest(container_name=container_name, cmd_json=cmd_json, run_id=run_id, env=env)
        )

    def cancel_run(self, agent_id: str, container_name: str, run_id: str) -> None:
        conn = self._registry.pick(agent_id)
        self._drain_void(
            conn.request(
                CancelRunRequest(container_name=container_name, run_id=run_id),
                frame_gap_timeout=QUICK_OP_TIMEOUT,
            )
        )

    # ------------------------------------------------
    # Request/response — materialise the terminal frame.
    # ------------------------------------------------

    def remove(self, agent_id: str, ree_id: str, location: WorkbenchLocation) -> None:
        # Best-effort cleanup: never let a teardown failure propagate.
        try:
            conn = self._registry.pick(agent_id)
        except WorkbenchUnavailableError:
            return
        try:
            self._drain_void(
                conn.request(RemoveRequest(ree_id=ree_id, location=location), frame_gap_timeout=QUICK_OP_TIMEOUT)
            )
        except (WorkbenchUnavailableError, RuntimeError):
            pass

    def is_running(self, agent_id: str, container_name: str) -> bool:
        try:
            conn = self._registry.pick(agent_id)
        except WorkbenchUnavailableError:
            return False
        try:
            frames = conn.request(
                IsRunningRequest(container_name=container_name),
                frame_gap_timeout=QUICK_OP_TIMEOUT,
            )
            for frame in frames:
                if isinstance(frame, RunningFrame):
                    return frame.running
                if isinstance(frame, ErrorFrame | UnavailableFrame):
                    return False
        except WorkbenchUnavailableError:
            return False
        return False

    def exec_simple(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 60) -> None:
        conn = self._registry.pick(agent_id)
        req = ExecSimpleRequest(container_name=container_name, argv=argv, timeout=timeout)
        # The agent enforces ``timeout`` on the exec itself; the frame gap only
        # needs to cover it plus transport slack.
        self._drain_void(conn.request(req, frame_gap_timeout=timeout + QUICK_OP_TIMEOUT))

    def exec_query(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 30) -> bytes:
        return b"".join(self.exec_query_stream(agent_id, container_name, argv, timeout))

    def exec_query_stream(
        self, agent_id: str, container_name: str, argv: list[str], timeout: int = 30
    ) -> Iterator[bytes]:
        # The result arrives as bounded chunks ending in ``done``; yield each
        # decoded chunk so large archives do not materialise in control-plane RAM.
        conn = self._registry.pick(agent_id)
        for frame in conn.request(
            ExecQueryRequest(container_name=container_name, argv=argv, timeout=timeout),
            frame_gap_timeout=timeout + QUICK_OP_TIMEOUT,
        ):
            if isinstance(frame, BytesChunkFrame):
                yield base64.b64decode(frame.data_b64)
            elif isinstance(frame, DoneFrame):
                return
            else:
                raise_for_terminal_error(frame)
        raise RuntimeError("agent exec_query ended without a result")

    def copy_in(self, agent_id: str, container_name: str, source_path: str, container_path: str) -> None:
        # Chunked copy-in (see repo2ree_protocol.agent), read straight from disk.
        # Chunks are pipelined: up to COPY_IN_WINDOW ride the wire before the
        # oldest ack is drained, so throughput is bound by bandwidth, not by one
        # round trip per chunk. Each chunk carries its offset, so the agent can
        # apply them in whatever order they land.
        # On any failure, tell the agent to drop its partial temp file.
        conn = self._registry.pick(agent_id)
        transfer_id = self._open_transfer(conn, container_name, container_path)
        in_flight: deque[PendingReply] = deque()
        try:
            with open(source_path, "rb") as source:
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
            # copy_close runs `docker cp` of the assembled file on the agent;
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

    def _open_transfer(self, conn: AgentConnection, container_name: str, container_path: str) -> str:
        req = CopyOpenRequest(container_name=container_name, container_path=container_path)
        for frame in conn.request(req, frame_gap_timeout=QUICK_OP_TIMEOUT):
            if isinstance(frame, TransferFrame):
                return frame.transfer_id
            raise_for_terminal_error(frame)
        raise RuntimeError("agent copy_open ended without a transfer id")

    def _drain_void(self, frames: Iterator[AgentFrame]) -> None:
        """Consume a stream whose only meaningful outcome is success or error."""
        for frame in frames:
            raise_for_terminal_error(frame)
