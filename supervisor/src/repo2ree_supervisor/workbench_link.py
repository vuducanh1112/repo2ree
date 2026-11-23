from __future__ import annotations

import base64
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import (
    TERMINAL_FRAME_TYPES,
    BytesChunkFrame,
    DoneFrame,
    Frame,
    SpanFrame,
    UnavailableFrame,
)
from repo2ree_protocol.queries import BundleQuery, InitRee, Query
from repo2ree_protocol.workbench import (
    CancelRequest,
    CancelRunRequest,
    DeleteReeRequest,
    ExecQueryRequest,
    ExecUploadRequest,
    FetchFileRequest,
    FollowRunRequest,
    InitReeRequest,
    ListJournalsRequest,
    ReadJournalRequest,
    StartRunRequest,
    WorkbenchHello,
    WorkbenchJournalList,
    WorkbenchRequest,
    WorkbenchWsRequest,
    workbench_ws_message_adapter,
)
from repo2ree_supervisor.client import WorkbenchUnavailableError, raise_for_terminal_error
from repo2ree_supervisor.sessions import Session
from repo2ree_supervisor.transfers import ReceivedFile, Transfers
from repo2ree_telemetry.behaviour.events import WorkbenchSessionReason
from repo2ree_telemetry.relay import SpanSink
from repo2ree_telemetry.spans import current_traceparent

logger = logging.getLogger(__name__)


DEFAULT_FRAME_GAP_TIMEOUT = 900.0

QUICK_OP_TIMEOUT = 30.0

COPY_IN_TIMEOUT = 600.0


@dataclass(frozen=True)
class WorkbenchInfo:
    workbench_id: str
    hostname: str
    version: str
    store_id: str
    connected_at: float
    build: BuildInfo = field(default_factory=BuildInfo)
    executor_build: BuildInfo = field(default_factory=BuildInfo)


class WorkbenchConnection:
    def __init__(
        self,
        send_text: Callable[[str], None],
        hello: WorkbenchHello | None = None,
        *,
        span_sink: SpanSink | None = None,
        session: Session | None = None,
    ):
        self._send_text = send_text
        self.hello = hello
        self._span_sink = span_sink
        self.session = session
        self._pending: dict[str, queue.Queue[Frame]] = {}
        self._lock = threading.Lock()
        self._closed = False

    def on_message(self, text: str) -> None:
        message = workbench_ws_message_adapter.validate_json(text)
        if message.id is None:
            if isinstance(message.frame, SpanFrame) and self._span_sink is not None:
                self._span_sink([message.frame.payload])
            return
        with self._lock:
            q = self._pending.get(message.id)
        if q is not None:
            q.put(message.frame)

    def request(
        self, request: WorkbenchRequest, *, frame_gap_timeout: float | None = DEFAULT_FRAME_GAP_TIMEOUT
    ) -> Iterator[Frame]:
        yield from self.start(request).frames(frame_gap_timeout=frame_gap_timeout)

    def start(self, request: WorkbenchRequest) -> PendingReply:
        req_id = uuid4().hex
        q: queue.Queue[Frame] = queue.Queue()
        with self._lock:
            if self._closed:
                raise WorkbenchUnavailableError("workbench connection closed")
            self._pending[req_id] = q
        try:
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
        with self._lock:
            if self._closed:
                return
        with suppress(Exception):
            self._send_text(
                WorkbenchWsRequest(id=uuid4().hex, request=CancelRequest(request_id=req_id)).model_dump_json()
            )

    @property
    def session_id(self) -> str | None:
        return self.session.session_id if self.session is not None else None

    def close(self, reason: WorkbenchSessionReason = "closed", close_code: int | None = None) -> None:
        if self.session is not None:
            self.session.lose(reason, close_code)
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for q in pending:
            q.put(UnavailableFrame(detail="workbench connection closed"))


class PendingReply:
    def __init__(self, connection: WorkbenchConnection, req_id: str, q: queue.Queue[Frame], op: str):
        self._connection = connection
        self._req_id = req_id
        self._queue = q
        self._op = op

    def frames(self, *, frame_gap_timeout: float | None = DEFAULT_FRAME_GAP_TIMEOUT) -> Iterator[Frame]:
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
            self._connection._discard(self._req_id)  # noqa: SLF001
            if not terminated:
                self._connection._cancel(self._req_id)  # noqa: SLF001

    def discard(self) -> None:
        self._connection._discard(self._req_id)  # noqa: SLF001


class StoreClaimedError(RuntimeError):
    pass


class WorkbenchConnectionRegistry:
    def __init__(self) -> None:
        self._workbenches: dict[str, WorkbenchConnection] = {}
        self._connected_at: dict[str, float] = {}
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)

    def register(self, workbench_id: str, connection: WorkbenchConnection) -> None:
        store_id = connection.hello.store_id if connection.hello else ""
        with self._lock:
            if store_id and (holder := self._store_holder_locked(store_id)) not in {None, workbench_id}:
                raise StoreClaimedError(f"store {store_id!r} is already served by workbench {holder!r}")
            displaced = self._workbenches.get(workbench_id)
            self._workbenches[workbench_id] = connection
            self._connected_at[workbench_id] = time.time()
            self._changed.notify_all()
        if displaced is not None and displaced is not connection:
            self._log_displacement(workbench_id, displaced, connection)
            displaced.close("superseded")

    @staticmethod
    def _log_displacement(workbench_id: str, displaced: WorkbenchConnection, connection: WorkbenchConnection) -> None:
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

    def store_workbench(self, store_id: str) -> str | None:
        with self._lock:
            return self._store_holder_locked(store_id)

    def _store_holder_locked(self, store_id: str) -> str | None:
        return next(
            (
                workbench_id
                for workbench_id, connection in self._workbenches.items()
                if connection.hello is not None and connection.hello.store_id == store_id
            ),
            None,
        )

    def unregister(self, workbench_id: str, connection: WorkbenchConnection) -> None:
        with self._lock:
            if self._workbenches.get(workbench_id) is connection:
                self._workbenches.pop(workbench_id, None)
                self._connected_at.pop(workbench_id, None)
                self._changed.notify_all()

    def close_all(self, reason: WorkbenchSessionReason) -> None:
        with self._lock:
            connections = list(self._workbenches.values())
        for connection in connections:
            connection.close(reason)

    def wait(self, workbench_id: str, timeout: float) -> None:
        with self._changed:
            if not self._changed.wait_for(lambda: workbench_id in self._workbenches, timeout):
                raise WorkbenchUnavailableError(f"workbench {workbench_id!r} did not connect within {timeout:g}s")

    def pick(self, workbench_id: str | None = None) -> WorkbenchConnection:
        with self._lock:
            return self._workbenches[self._resolve_locked(workbench_id)]

    def resolve(self, workbench_id: str | None = None) -> str:
        with self._lock:
            return self._resolve_locked(workbench_id)

    def _resolve_locked(self, workbench_id: str | None) -> str:
        if workbench_id:
            if workbench_id not in self._workbenches:
                raise WorkbenchUnavailableError(f"workbench {workbench_id!r} not connected")
            return workbench_id
        for connected_id in self._workbenches:
            return connected_id
        raise WorkbenchUnavailableError("no workbench service connected")

    def list_workbenches(self) -> list[WorkbenchInfo]:
        with self._lock:
            infos = [
                WorkbenchInfo(
                    workbench_id=workbench_id,
                    hostname=conn.hello.hostname if conn.hello else "",
                    version=conn.hello.version if conn.hello else "",
                    build=conn.hello.build if conn.hello else BuildInfo(),
                    executor_build=conn.hello.executor_build if conn.hello else BuildInfo(),
                    store_id=conn.hello.store_id if conn.hello else "",
                    connected_at=self._connected_at.get(workbench_id, 0.0),
                )
                for workbench_id, conn in self._workbenches.items()
            ]
        infos.sort(key=lambda info: (info.hostname, info.workbench_id))
        return infos


class WsWorkbenchClient:
    def __init__(self, registry: WorkbenchConnectionRegistry, transfers: Transfers | None = None):
        self._registry = registry
        self._transfers = transfers if transfers is not None else Transfers()

    def resolve_workbench(self, workbench_id: str) -> str:
        return self._registry.resolve(workbench_id)

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        self._registry.wait(workbench_id, timeout)

    def is_connected(self, workbench_id: str) -> bool:
        try:
            self._registry.pick(workbench_id)
        except WorkbenchUnavailableError:
            return False
        return True

    def is_running(self, workbench_id: str) -> bool:
        return self.is_connected(workbench_id)

    def session_of(self, workbench_id: str) -> str | None:
        try:
            return self._registry.pick(workbench_id).session_id
        except WorkbenchUnavailableError:
            return None

    def start_run(
        self,
        workbench_id: str,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext,
        *,
        ree_id: str,
        session: str | None = None,
        wait: float = 0.0,
    ) -> Iterator[Frame]:
        connection = self._on_session(workbench_id, session)
        return connection.request(
            StartRunRequest(cmd_json=cmd_json, run_id=run_id, env=env, context=context, ree_id=ree_id, wait=wait),
            frame_gap_timeout=None,
        )

    def follow_run(
        self, workbench_id: str, attempt_id: str, after: int, *, ree_id: str, session: str | None = None
    ) -> Iterator[Frame]:
        connection = self._on_session(workbench_id, session)
        return connection.request(
            FollowRunRequest(ree_id=ree_id, attempt_id=attempt_id, after=after), frame_gap_timeout=None
        )

    def _on_session(self, workbench_id: str, session: str | None) -> WorkbenchConnection:
        connection = self._registry.pick(workbench_id)
        if session is not None and connection.session_id != session:
            raise WorkbenchUnavailableError(f"session {session} ended before the request was sent")
        return connection

    def cancel_run(self, workbench_id: str, run_id: str, *, ree_id: str, record: str | None = None) -> None:
        conn = self._registry.pick(workbench_id)
        self._drain_void(
            conn.request(
                CancelRunRequest(run_id=run_id, ree_id=ree_id, record=record),
                frame_gap_timeout=QUICK_OP_TIMEOUT,
            )
        )

    def delete_ree(self, workbench_id: str, ree_id: str) -> None:
        conn = self._registry.pick(workbench_id)
        self._drain_void(conn.request(DeleteReeRequest(ree_id=ree_id), frame_gap_timeout=COPY_IN_TIMEOUT))

    def init_ree(self, workbench_id: str, init: InitRee, timeout: int = 60, *, ree_id: str) -> None:
        conn = self._registry.pick(workbench_id)
        req = InitReeRequest(init=init, timeout=timeout, ree_id=ree_id)
        self._drain_void(conn.request(req, frame_gap_timeout=timeout + QUICK_OP_TIMEOUT))

    def exec_query(self, workbench_id: str, query: Query, timeout: int = 30, *, ree_id: str) -> bytes:
        return b"".join(self.exec_query_stream(workbench_id, query, timeout, ree_id=ree_id))

    def exec_query_stream(self, workbench_id: str, query: Query, timeout: int = 30, *, ree_id: str) -> Iterator[bytes]:
        conn = self._registry.pick(workbench_id)
        for frame in conn.request(
            ExecQueryRequest(query=query, timeout=timeout, ree_id=ree_id),
            frame_gap_timeout=timeout + QUICK_OP_TIMEOUT,
        ):
            if isinstance(frame, BytesChunkFrame):
                yield base64.b64decode(frame.data_b64)
            elif isinstance(frame, DoneFrame):
                return
            else:
                raise_for_terminal_error(frame)
        raise RuntimeError("workbench exec_query ended without a result")

    def exec_upload(self, workbench_id: str, query: BundleQuery, timeout: int = 600, *, ree_id: str) -> ReceivedFile:
        conn = self._registry.pick(workbench_id)
        transfer_path = self._transfers.open_upload()
        try:
            for frame in conn.request(
                ExecUploadRequest(query=query, transfer_path=transfer_path, timeout=timeout, ree_id=ree_id),
                frame_gap_timeout=timeout + QUICK_OP_TIMEOUT,
            ):
                if isinstance(frame, DoneFrame):
                    return self._transfers.collect(transfer_path)
                raise_for_terminal_error(frame)
            raise RuntimeError("workbench exec_upload ended without a result")
        finally:
            self._transfers.discard(transfer_path)

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        conn = self._registry.pick(workbench_id)
        transfer_path = self._transfers.offer(Path(source_path))
        try:
            self._drain_void(
                conn.request(
                    FetchFileRequest(transfer_path=transfer_path, workbench_path=workbench_path, ree_id=ree_id),
                    frame_gap_timeout=COPY_IN_TIMEOUT,
                )
            )
        finally:
            self._transfers.close(transfer_path)

    def list_journals(self, workbench_id: str) -> WorkbenchJournalList:
        conn = self._registry.pick(workbench_id)
        listed = b"".join(self._drain_bytes(conn.request(ListJournalsRequest(), frame_gap_timeout=QUICK_OP_TIMEOUT)))
        return WorkbenchJournalList.model_validate_json(listed)

    def read_journal(self, workbench_id: str, journal_id: str, after: int = 0) -> Iterator[bytes]:
        conn = self._registry.pick(workbench_id)
        request = ReadJournalRequest(journal_id=journal_id, after=after)
        yield from self._drain_bytes(conn.request(request, frame_gap_timeout=COPY_IN_TIMEOUT))

    @staticmethod
    def _drain_bytes(frames: Iterator[Frame]) -> Iterator[bytes]:
        for frame in frames:
            if isinstance(frame, BytesChunkFrame):
                yield base64.b64decode(frame.data_b64)
            elif isinstance(frame, DoneFrame):
                return
            else:
                raise_for_terminal_error(frame)
        raise RuntimeError("workbench stream ended without a result")

    def _drain_void(self, frames: Iterator[Frame]) -> None:
        for frame in frames:
            raise_for_terminal_error(frame)
