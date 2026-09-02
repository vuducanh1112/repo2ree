"""The workbench-dialed WebSocket bridge, driven by an in-memory transport.

No real socket: a fake ``send_text`` captures outbound ``WsRequest``s, and a
helper feeds ``WsMessage`` responses back through ``on_message`` — the same path
the API's WebSocket route uses. Requests run in a worker thread (as the real
synchronous manager would) so the blocking ``request()`` and the frame-feeding
happen concurrently, exactly like production.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Iterator
from typing import Any, Protocol, cast

import pytest

from repo2ree_protocol.frames import (
    BytesChunkFrame,
    DoneFrame,
    ErrorFrame,
    LogFrame,
    ResultFrame,
    TransferFrame,
    UnavailableFrame,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import (
    CopyChunkRequest,
    WorkbenchWsMessage,
    WorkbenchWsRequest,
    workbench_ws_request_adapter,
)
from repo2ree_supervisor import (
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
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    frames: list[Any] = []
    join = _run_in_thread(lambda: frames.extend(client.exec_action("a1", "{}", "run1", {})))
    socket.wait_for_request()
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


def test_copy_in_streams_open_chunks_then_close(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"streamed-archive-bytes")

    join = _run_in_thread(lambda: client.copy_in("a1", str(source), "/ree/dest.bin"))

    open_req = socket.wait_for_nth_request(1).request
    assert open_req.op == "copy_open"
    assert open_req.workbench_path == "/ree/dest.bin"
    socket.respond_to(0, TransferFrame(transfer_id="t1"))

    # Payload is smaller than one chunk, so a single copy_chunk carries it all.
    chunk_req = socket.wait_for_nth_request(2).request
    assert chunk_req.op == "copy_chunk"
    assert chunk_req.transfer_id == "t1"
    assert chunk_req.offset == 0
    assert base64.b64decode(chunk_req.data_b64) == b"streamed-archive-bytes"
    socket.respond_to(1, DoneFrame())

    close_req = socket.wait_for_nth_request(3).request
    assert close_req.op == "copy_close"
    assert close_req.transfer_id == "t1"
    socket.respond_to(2, DoneFrame())

    join()
    assert [req.request.op for req in socket.sent] == ["copy_open", "copy_chunk", "copy_close"]


def test_copy_in_pipelines_chunks_within_the_window(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Every chunk of a windowed transfer rides the wire before the first ack
    # comes back — throughput must not be one round trip per chunk. Offsets
    # address the writes so the workbench can apply them in any order.
    import repo2ree_supervisor.workbench_link as workbench_link_module

    monkeypatch.setattr(workbench_link_module, "COPY_CHUNK_BYTES", 4)
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"0123456789")  # 3 chunks: 4 + 4 + 2 bytes

    join = _run_in_thread(lambda: client.copy_in("a1", str(source), "/ree/dest.bin"))
    socket.wait_for_nth_request(1)
    socket.respond_to(0, TransferFrame(transfer_id="t1"))

    # All three chunks arrive with no ack sent yet (window is larger than 3).
    socket.wait_for_nth_request(4)
    raw_chunk_reqs = [req.request for req in socket.sent[1:4]]
    assert [req.op for req in raw_chunk_reqs] == ["copy_chunk"] * 3
    assert all(isinstance(req, CopyChunkRequest) for req in raw_chunk_reqs)
    chunk_reqs = cast("list[CopyChunkRequest]", raw_chunk_reqs)
    assert [req.offset for req in chunk_reqs] == [0, 4, 8]
    assert b"".join(base64.b64decode(req.data_b64) for req in chunk_reqs) == b"0123456789"

    for index in (1, 2, 3):
        socket.respond_to(index, DoneFrame())
    close_req = socket.wait_for_nth_request(5).request
    assert close_req.op == "copy_close"
    socket.respond_to(4, DoneFrame())
    join()


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


def test_copy_in_aborts_transfer_on_chunk_error(tmp_path) -> None:
    socket = FakeSocket()
    registry = WorkbenchConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsWorkbenchClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"some-bytes")

    join = _run_in_thread(lambda: client.copy_in("a1", str(source), "/ree/dest.bin"))

    socket.wait_for_nth_request(1)
    socket.respond_to(0, TransferFrame(transfer_id="t9"))
    socket.wait_for_nth_request(2)
    # The workbench rejects a chunk: the client must abort the transfer and re-raise.
    socket.respond_to(1, ErrorFrame(detail="disk full"))

    abort_req = socket.wait_for_nth_request(3).request
    assert abort_req.op == "copy_abort"
    assert abort_req.transfer_id == "t9"
    socket.respond_to(2, DoneFrame())

    with pytest.raises(RuntimeError, match="disk full"):
        join()


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
