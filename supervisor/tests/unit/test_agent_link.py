"""The agent-dialed WebSocket bridge, driven by an in-memory transport.

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
from typing import Protocol, cast

import pytest

from repo2ree_protocol.agent import (
    BytesChunkFrame,
    CopyChunkRequest,
    DoneFrame,
    ErrorFrame,
    IsRunningRequest,
    LocationFrame,
    LogFrame,
    ResultFrame,
    RunningFrame,
    TransferFrame,
    UnavailableFrame,
    WorkbenchLocation,
    WsMessage,
    WsRequest,
    ws_request_adapter,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import AgentConnection, AgentConnectionRegistry, WorkbenchUnavailableError, WsAgentClient


class _ClosableIterator(Iterator[bytes], Protocol):
    def close(self) -> None: ...


class FakeSocket:
    """Captures outbound requests and lets a test push responses back."""

    def __init__(self) -> None:
        self.connection = AgentConnection(send_text=self._capture)
        self.sent: list[WsRequest] = []
        self._cond = threading.Condition()

    def _capture(self, text: str) -> None:
        with self._cond:
            self.sent.append(ws_request_adapter.validate_json(text))
            self._cond.notify_all()

    def wait_for_request(self, timeout: float = 2.0) -> WsRequest:
        return self.wait_for_nth_request(1, timeout)

    def wait_for_nth_request(self, n: int, timeout: float = 2.0) -> WsRequest:
        """Block until at least ``n`` requests have been sent; return the n-th."""
        with self._cond:
            assert self._cond.wait_for(lambda: len(self.sent) >= n, timeout), f"request #{n} was not sent"
            return self.sent[n - 1]

    def respond(self, frame) -> None:
        self.respond_to(-1, frame)

    def respond_to(self, index: int, frame) -> None:
        req_id = self.sent[index].id
        self.connection.on_message(WsMessage(id=req_id, frame=frame).model_dump_json())


def _run_in_thread(fn):
    """Run a blocking client call in a thread; return a getter for its result."""
    box: dict = {}

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
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", "wb", ["get-ree"]))
    req = socket.wait_for_request()
    assert req.request.op == "exec_query"
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b'{"ok": true}').decode()))
    socket.respond(DoneFrame())

    assert join() == b'{"ok": true}'


def test_exec_query_raises_on_unavailable() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", "wb", ["get-ree"]))
    socket.wait_for_request()
    socket.respond(UnavailableFrame(detail="gone"))

    with pytest.raises(WorkbenchUnavailableError, match="gone"):
        join()


def test_provision_stream_yields_until_terminal_location() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    frames: list = []
    join = _run_in_thread(lambda: frames.extend(client.provision("a1", "ree1", "img:tag")))
    socket.wait_for_request()
    socket.respond(LogFrame(stream="system", level="info", message="pulling"))
    socket.respond(LocationFrame(location=WorkbenchLocation(container_name="wb-ree1", volume_name="vol-ree1")))
    join()

    assert isinstance(frames[0], LogFrame)
    assert isinstance(frames[-1], LocationFrame)
    assert frames[-1].location.container_name == "wb-ree1"


def test_is_running_true_and_no_agent_false() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    client = WsAgentClient(registry)

    # No agent connected → False, no raise.
    assert client.is_running("a1", "wb") is False

    registry.register("a1", socket.connection)
    join = _run_in_thread(lambda: client.is_running("a1", "wb"))
    socket.wait_for_request()
    socket.respond(RunningFrame(running=True))
    assert join() is True


def test_exec_action_streams_logs_then_result() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    frames: list = []
    join = _run_in_thread(lambda: frames.extend(client.exec_action("a1", "wb", "{}", "run1", {})))
    socket.wait_for_request()
    socket.respond(LogFrame(stream="stdout", level="info", message="working"))
    socket.respond(ResultFrame(result=ActionResult(status="succeeded")))
    join()

    assert isinstance(frames[0], LogFrame)
    assert isinstance(frames[-1], ResultFrame)
    assert frames[-1].result.status == "succeeded"


def test_cancel_run_sends_cancel_run_request() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    join = _run_in_thread(lambda: client.cancel_run("a1", "wb", "run-7"))
    req = socket.wait_for_request()
    assert req.request.op == "cancel_run"
    assert req.request.container_name == "wb"
    assert req.request.run_id == "run-7"
    socket.respond(DoneFrame())
    join()


def test_copy_in_streams_open_chunks_then_close(tmp_path) -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"streamed-archive-bytes")

    join = _run_in_thread(lambda: client.copy_in("a1", "wb", str(source), "/ree/dest.bin"))

    open_req = socket.wait_for_nth_request(1).request
    assert open_req.op == "copy_open"
    assert open_req.container_name == "wb"
    assert open_req.container_path == "/ree/dest.bin"
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
    # address the writes so the agent can apply them in any order.
    import repo2ree_supervisor.agent_link as agent_link_module

    monkeypatch.setattr(agent_link_module, "COPY_CHUNK_BYTES", 4)
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"0123456789")  # 3 chunks: 4 + 4 + 2 bytes

    join = _run_in_thread(lambda: client.copy_in("a1", "wb", str(source), "/ree/dest.bin"))
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


def test_abandoned_stream_sends_cancel_to_the_agent() -> None:
    # A consumer that walks away mid-stream (a client dropping a download) must
    # tell the agent to stop producing, or the workbench keeps doing the work
    # for no one.
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    def call() -> None:
        stream = cast(_ClosableIterator, client.exec_query_stream("a1", "wb", ["build-archive"]))
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
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    source = tmp_path / "archive.bin"
    source.write_bytes(b"some-bytes")

    join = _run_in_thread(lambda: client.copy_in("a1", "wb", str(source), "/ree/dest.bin"))

    socket.wait_for_nth_request(1)
    socket.respond_to(0, TransferFrame(transfer_id="t9"))
    socket.wait_for_nth_request(2)
    # The agent rejects a chunk: the client must abort the transfer and re-raise.
    socket.respond_to(1, ErrorFrame(detail="disk full"))

    abort_req = socket.wait_for_nth_request(3).request
    assert abort_req.op == "copy_abort"
    assert abort_req.transfer_id == "t9"
    socket.respond_to(2, DoneFrame())

    with pytest.raises(RuntimeError, match="disk full"):
        join()


def test_resolve_agent_pins_empty_placement_to_a_concrete_agent() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    # An empty ("any agent") request resolves to the concrete connected id, so a
    # provision can pin the REE to it rather than to "".
    assert client.resolve_agent("") == "a1"
    # A named agent resolves to itself.
    assert client.resolve_agent("a1") == "a1"


def test_resolve_agent_raises_when_no_agent_connected() -> None:
    client = WsAgentClient(AgentConnectionRegistry())
    with pytest.raises(WorkbenchUnavailableError, match="no workbench agent connected"):
        client.resolve_agent("")


def test_pick_raises_when_no_agent_for_exec_query() -> None:
    client = WsAgentClient(AgentConnectionRegistry())
    with pytest.raises(WorkbenchUnavailableError, match="no workbench agent connected"):
        client.exec_query("", "wb", ["get-ree"])


def test_pick_raises_when_named_agent_absent() -> None:
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)
    # A different agent is connected, but the REE is pinned to one that isn't.
    with pytest.raises(WorkbenchUnavailableError, match="agent 'a2' not connected"):
        client.exec_query("a2", "wb", ["get-ree"])


def test_request_times_out_when_agent_goes_silent() -> None:
    # A connected-but-unresponsive agent (suspended process, hung docker call)
    # must surface as unavailable, not block the calling thread forever.
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)

    def call() -> None:
        for _ in socket.connection.request(IsRunningRequest(container_name="wb"), frame_gap_timeout=0.1):
            pass

    join = _run_in_thread(call)
    socket.wait_for_request()  # the request went out; the agent never answers
    with pytest.raises(WorkbenchUnavailableError, match="stopped responding"):
        join()


def test_is_running_returns_false_when_agent_goes_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    # The client-level wrapper maps the silence timeout to a plain False, the
    # same answer an absent agent gets.
    import repo2ree_supervisor.agent_link as agent_link_module

    monkeypatch.setattr(agent_link_module, "QUICK_OP_TIMEOUT", 0.1)
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    join = _run_in_thread(lambda: client.is_running("a1", "wb"))
    socket.wait_for_request()  # sent, but the agent never answers
    assert join() is False


def test_exec_query_reassembles_multiple_chunks() -> None:
    # Large results (a sealed archive) arrive as many bounded chunks; the
    # client must reassemble them in order.
    socket = FakeSocket()
    registry = AgentConnectionRegistry()
    registry.register("a1", socket.connection)
    client = WsAgentClient(registry)

    join = _run_in_thread(lambda: client.exec_query("a1", "wb", ["build-archive"]))
    socket.wait_for_request()
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b"part-one-").decode()))
    socket.respond(BytesChunkFrame(data_b64=base64.b64encode(b"part-two").decode()))
    socket.respond(DoneFrame())

    assert join() == b"part-one-part-two"
