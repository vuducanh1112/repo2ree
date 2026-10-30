"""The workbench-dialed WebSocket bridge, driven by an in-memory transport.

No real socket: a fake ``send_text`` captures outbound ``WsRequest``s, and a
helper feeds ``WsMessage`` responses back through ``on_message`` — the same path
the API's WebSocket route uses. Requests run in a worker thread (as the real
synchronous manager would) so the blocking ``request()`` and the frame-feeding
happen concurrently, exactly like production.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any, Protocol, cast

import pytest

from repo2ree_protocol.frames import (
    BytesChunkFrame,
    DoneFrame,
    ErrorFrame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import (
    ExecActionRequest,
    ExecSimpleRequest,
    ExecUploadRequest,
    FetchFileRequest,
    WorkbenchWsMessage,
    WorkbenchWsRequest,
    workbench_ws_request_adapter,
)
from repo2ree_supervisor import (
    ReceivedFile,
    TransferError,
    Transfers,
    WorkbenchConnection,
    WorkbenchConnectionRegistry,
    WorkbenchUnavailableError,
    WsWorkbenchClient,
)


class _ClosableIterator(Iterator[bytes], Protocol):
    def close(self) -> None: ...


class FakeSocket:
    """Captures outbound requests and lets a test push responses back."""

    def __init__(self) -> None:
        self.connection = WorkbenchConnection(send_text=self._capture)
        self.sent: list[WorkbenchWsRequest] = []
        self._cond = threading.Condition()

    def _capture(self, text: str) -> None:
        with self._cond:
            self.sent.append(workbench_ws_request_adapter.validate_json(text))
            self._cond.notify_all()

    def wait_for_request(self, timeout: float = 2.0) -> WorkbenchWsRequest:
        return self.wait_for_nth_request(1, timeout)

    def wait_for_nth_request(self, n: int, timeout: float = 2.0) -> WorkbenchWsRequest:
        """Block until at least ``n`` requests have been sent; return the n-th."""
        with self._cond:
            assert self._cond.wait_for(lambda: len(self.sent) >= n, timeout), f"request #{n} was not sent"
            return self.sent[n - 1]

    def respond(self, frame) -> None:
        self.respond_to(-1, frame)

    def respond_to(self, index: int, frame) -> None:
        req_id = self.sent[index].id
        self.connection.on_message(WorkbenchWsMessage(id=req_id, frame=frame).model_dump_json())


def _run_in_thread(fn):
    """Run a blocking client call in a thread; return a getter for its result."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — re-raised in the test thread
            box["error"] = exc

    thread = threading.Thread(target=target)
    thread.start()

    def join():
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "client call did not complete"
        if "error" in box:
            raise box["error"]
        return box.get("value")

    return join


def test_exec_query_returns_decoded_bytes() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", ["get-ree-manifest"]))
    req = socket.wait_for_request()
    assert req.request.op == "exec_query"
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b'{"ok": true}').decode()))
    socket.respond(DoneFrame())

    assert join() == b'{"ok": true}'


def test_exec_query_raises_on_unavailable() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", ["get-ree-manifest"]))
    socket.wait_for_request()
    socket.respond(UnavailableFrame(detail="gone"))

    with pytest.raises(WorkbenchUnavailableError, match="gone"):
        join()


def test_is_running_true_and_no_workbench_false() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    client = WsWorkbenchClient(registry)

    # No workbench connected → False, no raise.
    assert client.is_running("a1") is False

    registry.register("a1", socket.connection)
    assert client.is_running("a1") is True


def test_exec_action_streams_logs_then_result() -> None:
    from repo2ree_protocol.execution import ExecutionContext

    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    frames: list[Any] = []
    context = ExecutionContext.new(ree_id="ree-1")
    join = _run_in_thread(lambda: frames.extend(client.exec_action("a1", "{}", "run1", {}, context)))
    request = socket.wait_for_request()
    assert isinstance(request.request, ExecActionRequest)
    assert request.request.context == context
    socket.respond(LogFrame(stream="stdout", level="info", message="working"))
    socket.respond(ResultFrame(result=ActionResult(status="succeeded")))
    join()

    assert isinstance(frames[0], LogFrame)
    assert isinstance(frames[-1], ResultFrame)
    assert frames[-1].result.status == "succeeded"


def test_cancel_run_sends_cancel_run_request() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    join = _run_in_thread(lambda: client.cancel_run("a1", "run-7"))
    req = socket.wait_for_request()
    assert req.request.op == "cancel_run"
    assert req.request.run_id == "run-7"
    socket.respond(DoneFrame())
    join()


def test_copy_in_offers_the_file_for_one_fetch_beside_the_socket(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    transfers = Transfers(tmp_path)
    client = WsWorkbenchClient(registry, transfers)
    source = tmp_path / "archive.bin"
    source.write_bytes(b"0123456789")

    join = _run_in_thread(lambda: client.copy_in("a1", str(source), "/ree/dest.bin"))
    request = socket.wait_for_request().request
    assert isinstance(request, FetchFileRequest)
    assert request.workbench_path == "/ree/dest.bin"
    # What the API's route hands the workbench for that path: the file, once.
    token = request.transfer_path.removeprefix("/workbench/transfers/")
    assert transfers.serve(token) == source
    with pytest.raises(TransferError):
        transfers.serve(token)
    socket.respond(DoneFrame())
    join()

    assert source.read_bytes() == b"0123456789"  # the caller's file stays


def test_abandoned_stream_sends_cancel_to_the_workbench() -> None:
    # A consumer that walks away mid-stream (a client dropping a download) must
    # tell the workbench to stop producing, or the workbench keeps doing the work
    # for no one.
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    def call() -> None:
        stream = cast(_ClosableIterator, client.exec_query_stream("a1", ["build-archive"]))
        next(stream)
        stream.close()

    join = _run_in_thread(call)
    query_req = socket.wait_for_request()
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b"first").decode()))
    join()

    cancel_req = socket.wait_for_nth_request(2)
    assert cancel_req.request.op == "cancel"
    assert cancel_req.request.request_id == query_req.id


def test_a_failed_fetch_closes_its_transfer_and_raises(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    transfers = Transfers(tmp_path)
    client = WsWorkbenchClient(registry, transfers)
    source = tmp_path / "archive.bin"
    source.write_bytes(b"some-bytes")

    join = _run_in_thread(lambda: client.copy_in("a1", str(source), "/ree/dest.bin"))
    request = socket.wait_for_request().request
    assert isinstance(request, FetchFileRequest)
    socket.respond(ErrorFrame(detail="disk full"))

    with pytest.raises(RuntimeError, match="disk full"):
        join()
    with pytest.raises(TransferError):
        transfers.serve(request.transfer_path.removeprefix("/workbench/transfers/"))


def test_resolve_workbench_pins_empty_placement_to_a_concrete_workbench() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    # An empty ("any workbench") request resolves to the concrete connected id, so a
    # provision can pin the REE to it rather than to "".
    assert client.resolve_workbench("") == "a1"
    # A named workbench resolves to itself.
    assert client.resolve_workbench("a1") == "a1"


def test_resolve_workbench_raises_when_none_connected() -> None:
    client = WsWorkbenchClient(WorkbenchConnectionRegistry())
    with pytest.raises(WorkbenchUnavailableError, match="no workbench service connected"):
        client.resolve_workbench("")


def test_pick_raises_when_no_workbench_for_exec_query() -> None:
    client = WsWorkbenchClient(WorkbenchConnectionRegistry())
    with pytest.raises(WorkbenchUnavailableError, match="no workbench service connected"):
        client.exec_query("", ["get-ree-manifest"])


def test_pick_raises_when_named_workbench_absent() -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)
    # A different workbench is connected, but the REE is pinned to one that isn't.
    with pytest.raises(WorkbenchUnavailableError, match="workbench 'a2' not connected"):
        client.exec_query("a2", ["get-ree-manifest"])


def test_exec_query_reassembles_multiple_chunks() -> None:
    # Large results (a sealed archive) arrive as many bounded chunks; the
    # client must reassemble them in order.
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", ["build-archive"]))
    socket.wait_for_request()
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b"part-one-").decode()))
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b"part-two").decode()))
    socket.respond(DoneFrame())

    assert join() == b"part-one-part-two"


# ================================================
# Unsolicited frames (a workbench's own telemetry)
# ================================================


def test_unsolicited_span_frame_reaches_the_span_sink() -> None:
    relayed: list[list[str]] = []
    connection = WorkbenchConnection(send_text=lambda _text: None, span_sink=relayed.append)

    connection.on_message(WorkbenchWsMessage(frame=SpanFrame(payload="c3Bhbg==")).model_dump_json())

    # No id: the workbench's own span answers no request, so the pending lookup
    # that routes every other frame would have dropped it.
    assert relayed == [["c3Bhbg=="]]


def test_unsolicited_frame_without_a_sink_is_dropped_quietly() -> None:
    connection = WorkbenchConnection(send_text=lambda _text: None)

    # A control plane with no collector configured still has workbenches
    # relaying to it; that must not fault the socket's read loop.
    connection.on_message(WorkbenchWsMessage(frame=SpanFrame(payload="c3Bhbg==")).model_dump_json())


def test_correlated_frames_still_reach_their_caller_when_a_sink_is_set() -> None:
    relayed: list[list[str]] = []
    socket = FakeSocket()
    socket.connection = WorkbenchConnection(send_text=socket._capture, span_sink=relayed.append)

    pending = socket.connection.start(ExecSimpleRequest(argv=["doctor"]))
    socket.wait_for_request()
    socket.connection.on_message(WorkbenchWsMessage(id=socket.sent[-1].id, frame=DoneFrame()).model_dump_json())

    assert [frame.type for frame in pending.frames()] == ["done"]
    assert relayed == []


async def _body(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


def test_an_upload_arrives_beside_the_socket_and_is_collected_on_done(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    inbox = Transfers(tmp_path)
    client = WsWorkbenchClient(registry, inbox)
    received: list[ReceivedFile] = []

    join = _run_in_thread(lambda: received.append(client.exec_upload("a1", ["build-archive"])))
    request = socket.wait_for_request().request
    assert isinstance(request, ExecUploadRequest)
    assert request.argv == ["build-archive"]
    # What the workbench PUTs to the path it was given, as the API's route receives it.
    token = request.transfer_path.removeprefix("/workbench/transfers/")
    asyncio.run(inbox.receive(token, _body(b"PK", b"zip-bytes"), 11))
    socket.respond(DoneFrame())
    join()

    [archive] = received
    assert archive.path.read_bytes() == b"PKzip-bytes"
    assert archive.size == 11
    assert archive.sha256 == hashlib.sha256(b"PKzip-bytes").hexdigest()


def test_done_without_an_upload_is_an_error_and_leaves_no_file(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry, Transfers(tmp_path))
    errors: list[Exception] = []

    def call() -> None:
        try:
            client.exec_upload("a1", ["build-archive"])
        except TransferError as exc:
            errors.append(exc)

    join = _run_in_thread(call)
    socket.wait_for_request()
    socket.respond(DoneFrame())
    join()

    assert errors
    assert list(tmp_path.iterdir()) == []


def test_a_failed_upload_request_discards_its_transfer(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    inbox = Transfers(tmp_path)
    client = WsWorkbenchClient(registry, inbox)
    errors: list[Exception] = []

    def call() -> None:
        try:
            client.exec_upload("a1", ["build-archive"])
        except RuntimeError as exc:
            errors.append(exc)

    join = _run_in_thread(call)
    request = socket.wait_for_request().request
    assert isinstance(request, ExecUploadRequest)
    socket.respond(ErrorFrame(detail="executor query failed"))
    join()

    assert [str(error) for error in errors] == ["executor query failed"]
    assert list(tmp_path.iterdir()) == []
    token = request.transfer_path.removeprefix("/workbench/transfers/")
    with pytest.raises(TransferError, match="no such open transfer"):
        asyncio.run(inbox.receive(token, _body(b"late"), 4))
