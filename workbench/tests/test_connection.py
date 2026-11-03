"""The control connection's request-serving loop, driven by a fake socket.

Exercises ``_serve`` directly: the fake yields inbound messages like a real
``async for ws`` would and captures outbound sends, so dispatch and its
failure modes are tested without a network or a Docker daemon.
"""

from __future__ import annotations

import asyncio
import base64
import tempfile
import threading
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

import repo2ree_workbench.connection as connection
from repo2ree_protocol.frames import COPY_CHUNK_BYTES, TERMINAL_FRAME_TYPES, ResultFrame, SpanFrame
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import (
    CancelRequest,
    CancelRunRequest,
    ExecActionRequest,
    ExecQueryRequest,
    WorkbenchWsRequest,
    workbench_hello_adapter,
    workbench_ws_message_adapter,
    workbench_ws_request_adapter,
)
from repo2ree_workbench.connection import _serve, run_workbench
from repo2ree_workbench.service import WorkbenchService


class FakeSocket:
    """Yields queued inbound messages; captures what the workbench sends back.

    Like a control plane, it hangs up only once every request it sent is answered (a request it
    canceled never is): a socket that ends takes the requests still in flight with it.
    """

    def __init__(self, messages: list[str]) -> None:
        self._messages = messages
        self.sent: list[str] = []
        self._awaited: set[str] = set()

    def __aiter__(self) -> FakeSocket:
        return self

    async def __anext__(self) -> str:
        if self._messages:
            message = self._messages.pop(0)
            self._expect_answer(message)
            return message
        for _ in range(100):
            if self._awaited <= self._answered():
                break
            await asyncio.sleep(0.01)
        raise StopAsyncIteration

    def _expect_answer(self, message: str) -> None:
        try:
            request = workbench_ws_request_adapter.validate_json(message)
        except ValidationError:
            return
        if isinstance(request.request, CancelRequest):
            self._awaited.discard(request.request.request_id)
        else:
            self._awaited.add(request.id)

    def _answered(self) -> set[str]:
        answered: set[str] = set()
        for text in self.sent:
            try:
                message = workbench_ws_message_adapter.validate_json(text)
            except ValidationError:
                continue  # the hello, not a reply
            if message.id is not None and message.frame.type in TERMINAL_FRAME_TYPES:
                answered.add(message.id)
        return answered

    async def send(self, text: str) -> None:
        self.sent.append(text)


class FakeExec:
    query_result: bytes = b""
    canceled_runs: ClassVar[list[str]] = []

    def __init__(self) -> None:
        # Every fake backend gets its own empty store.
        self._root = tempfile.TemporaryDirectory()
        self.root = Path(self._root.name)

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str):
        for offset in range(0, len(self.query_result), COPY_CHUNK_BYTES):
            yield self.query_result[offset : offset + COPY_CHUNK_BYTES]

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str) -> None:
        return None

    def cancel_run(self, run_id: str, *, ree_id: str) -> None:
        self.canceled_runs.append(run_id)


def _service(exec_backend: object | None = None) -> WorkbenchService:
    """A workbench serving a store, as the control plane finds it."""
    return WorkbenchService(exec_backend or FakeExec(), store_id="lab-1")  # type: ignore[arg-type]


async def _serve_and_settle(ws: FakeSocket) -> None:
    await asyncio.wait_for(_serve(ws, _service()), timeout=10.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [workbench_ws_message_adapter.validate_json(text) for text in ws.sent]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    ws = FakeSocket(
        [
            "this is not json",
            WorkbenchWsRequest(id="r1", request=CancelRunRequest(ree_id="ree-1", run_id="run-1")).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["r1"]
    assert messages[0].frame.type == "done"


def test_unknown_op_answers_error_frame() -> None:
    # An op this workbench does not know (a version-skewed control plane) fails the
    # envelope's discriminated union; the id is still recoverable, so the caller
    # gets an error frame instead of hanging until its frame-gap timeout.
    ws = FakeSocket(['{"id": "r1", "request": {"op": "frobnicate"}}'])
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert messages[0].frame.type == "error"
    assert "frobnicate" in messages[0].frame.detail


def test_invalid_args_answer_error_frame_without_killing_connection() -> None:
    ws = FakeSocket(
        [
            '{"id": "r1", "request": {"op": "is_running", "wrong_field": "x"}}',
            WorkbenchWsRequest(id="r2", request=CancelRunRequest(ree_id="ree-1", run_id="run-2")).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["r1"].type == "error"
    assert by_id["r2"].type == "done"


def test_exec_query_result_is_chunked_under_the_frame_cap() -> None:
    # A large query result (a sealed archive) must never ride one frame: the
    # backend stream is forwarded as bounded frames and ends with ``done``.
    payload = bytes(range(256)) * 4 * 1024  # 1 MiB, above one chunk
    FakeExec.query_result = payload
    try:
        req = WorkbenchWsRequest(id="r1", request=ExecQueryRequest(ree_id="ree-1", argv=["build-archive"]))
        ws = FakeSocket([req.model_dump_json()])
        asyncio.run(_serve_and_settle(ws))
    finally:
        FakeExec.query_result = b""

    messages = _frames(ws)
    assert [m.frame.type for m in messages] == ["bytes_chunk"] * 4 + ["done"]
    reassembled = b"".join(base64.b64decode(m.frame.data_b64) for m in messages[:-1])
    assert reassembled == payload
    # No single serialized frame approaches the transport's 1 MiB receive cap.
    assert all(len(text) < 512 * 1024 for text in ws.sent)


def test_cancel_for_unknown_request_still_answers_done() -> None:
    # Cancel is idempotent: the target may have finished (or never existed) by
    # the time it arrives, and the canceller still deserves an answer.
    ws = FakeSocket([WorkbenchWsRequest(id="c1", request=CancelRequest(request_id="nope")).model_dump_json()])
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["c1"]
    assert messages[0].frame.type == "done"


def test_cancel_run_marks_run_in_workbench() -> None:
    FakeExec.canceled_runs = []
    ws = FakeSocket(
        [WorkbenchWsRequest(id="c1", request=CancelRunRequest(ree_id="ree-1", run_id="run-7")).model_dump_json()]
    )
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert messages[0].frame.type == "done"
    assert FakeExec.canceled_runs == ["run-7"]


def test_cancel_stops_an_inflight_request() -> None:
    # A cancelled request stops working and ships no frames; only the cancel
    # itself is answered. The backend call blocks so the request is still
    # in flight when the cancel lands.
    release = threading.Event()

    class BlockingExec(FakeExec):
        def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str):
            release.wait(0.5)
            yield b"too late"

    ws = FakeSocket(
        [
            WorkbenchWsRequest(
                id="r1", request=ExecQueryRequest(ree_id="ree-1", argv=["build-archive"])
            ).model_dump_json(),
            WorkbenchWsRequest(id="c1", request=CancelRequest(request_id="r1")).model_dump_json(),
        ]
    )
    try:
        asyncio.run(asyncio.wait_for(_serve(ws, _service(BlockingExec())), timeout=2.0))  # type: ignore[arg-type]
    finally:
        release.set()

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["c1"].type == "done"
    assert "r1" not in by_id


def test_a_lost_connection_stops_the_runs_it_was_waiting_for() -> None:
    # The socket ends with a build in flight: no one will read its result, so its run is canceled
    # and the connection is let go at once, not after the build.
    canceled = threading.Event()

    class RunningExec(FakeExec):
        def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str], context: object = None, *, ree_id: str):
            canceled.wait(5.0)
            yield ResultFrame(result=ActionResult(status="canceled"))

        def cancel_run(self, run_id: str, *, ree_id: str) -> None:
            super().cancel_run(run_id, ree_id=ree_id)
            canceled.set()

    FakeExec.canceled_runs = []
    request = ExecActionRequest(ree_id="ree-1", cmd_json="{}", run_id="run-1")
    # The build never answers on its own, so the socket hangs up with it in flight.
    ws = FakeSocket([WorkbenchWsRequest(id="b1", request=request).model_dump_json()])

    asyncio.run(asyncio.wait_for(_serve(ws, _service(RunningExec())), timeout=2.0))  # type: ignore[arg-type]

    assert FakeExec.canceled_runs == ["run-1"]


def test_stream_terminal_frame_drives_request_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    statuses: list[str] = []
    failures: list[object | None] = []
    exit_codes: list[int | None] = []
    active: list[tuple[int, dict[str, str]]] = []
    durations: list[dict[str, str]] = []
    monkeypatch.setattr(connection, "record_command_status", lambda span, status: statuses.append(status))
    monkeypatch.setattr(connection, "record_failure", lambda span, failure: failures.append(failure))
    monkeypatch.setattr(connection, "record_exit_code", lambda span, exit_code: exit_codes.append(exit_code))
    monkeypatch.setattr(connection._active_requests, "add", lambda value, attrs: active.append((value, attrs)))
    monkeypatch.setattr(connection._request_duration, "record", lambda value, attrs: durations.append(attrs))

    class TerminalExec(FakeExec):
        def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str], context=None, *, ree_id: str):
            yield ResultFrame(result=ActionResult.failed("execution", "command failed", origin="workbench"))

    request = ExecActionRequest(ree_id="ree-1", cmd_json="{}", run_id="run-1")
    ws = FakeSocket([WorkbenchWsRequest(id="r1", request=request).model_dump_json()])

    with caplog.at_level("WARNING", logger=connection.__name__):
        asyncio.run(asyncio.wait_for(_serve(ws, _service(TerminalExec())), timeout=2.0))  # type: ignore[arg-type]

    assert _frames(ws)[-1].frame.type == "result"
    assert statuses == ["failed"]
    assert [value for value, _ in active] == [1, -1]
    assert durations[-1]["repo2ree.status"] == "failed"
    assert "failed" in caplog.text
    assert failures[-1] is not None
    assert exit_codes[-1] == 1


def test_connection_hello_and_connected_gauge_are_balanced(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = FakeSocket([])
    connects = 0
    connected_values: list[int] = []

    class ConnectionContext:
        async def __aenter__(self) -> FakeSocket:
            return ws

        async def __aexit__(self, *args: object) -> None:
            return None

    def connect_once(url: str, **_options: float) -> ConnectionContext:
        nonlocal connects
        connects += 1
        if connects > 1:
            raise asyncio.CancelledError
        return ConnectionContext()

    class ConnectedGauge:
        def add(self, value: int, attrs: dict[str, str]) -> None:
            connected_values.append(value)

    monkeypatch.setattr(connection, "connect", connect_once)
    monkeypatch.setattr(connection, "_connected_gauge", ConnectedGauge())

    opaque_enrollment = "test-enrollment-value"
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_workbench(
                "ws://control/workbench/connect",
                _service(),
                "workbench-1",
                enrollment_token=opaque_enrollment,
            )
        )

    hello = workbench_hello_adapter.validate_json(ws.sent[0])
    assert hello.workbench_id == "workbench-1"
    assert hello.enrollment_token == opaque_enrollment
    assert hello.store_id == "lab-1"
    assert hello.nonce
    assert connected_values == [1, -1]


# ================================================
# Relaying the workbench's own spans
# ================================================


def test_the_span_relay_binds_only_after_the_hello(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = FakeSocket([])
    relay = connection.SpanRelay()
    connects = 0
    bound_when: list[int] = []

    class ConnectionContext:
        async def __aenter__(self) -> FakeSocket:
            return ws

        async def __aexit__(self, *args: object) -> None:
            return None

    def connect_once(url: str, **_options: float) -> ConnectionContext:
        nonlocal connects
        connects += 1
        if connects > 1:
            raise asyncio.CancelledError
        return ConnectionContext()

    real_bind = relay.bind

    def record_bind(loop, socket) -> None:
        bound_when.append(len(ws.sent))
        real_bind(loop, socket)

    monkeypatch.setattr(connection, "connect", connect_once)
    monkeypatch.setattr(relay, "bind", record_bind)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_workbench(
                "ws://control/workbench/connect",
                _service(),
                "workbench-1",
                span_relay=relay,
            )
        )

    # The control plane parses the first message on the socket as the hello, so
    # a span winning that race would be read as a malformed one and the
    # connection refused. Exactly one message — the hello — precedes the bind.
    assert bound_when == [1]
    assert workbench_hello_adapter.validate_json(ws.sent[0]).workbench_id == "workbench-1"


def test_the_span_relay_unbinds_when_the_connection_drops(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = FakeSocket([])
    relay = connection.SpanRelay()

    class ConnectionContext:
        async def __aenter__(self) -> FakeSocket:
            return ws

        async def __aexit__(self, *args: object) -> None:
            return None

    connects = 0

    def connect_once(url: str, **_options: float) -> ConnectionContext:
        nonlocal connects
        connects += 1
        if connects > 1:
            raise asyncio.CancelledError
        return ConnectionContext()

    monkeypatch.setattr(connection, "connect", connect_once)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_workbench("ws://control/workbench/connect", _service(), "workbench-1", span_relay=relay))

    # Unbound, so the exporter buffers for the next connection instead of
    # scheduling writes onto a dead socket.
    assert relay.send("c3Bhbg==") is False


def test_a_relayed_span_is_sent_uncorrelated() -> None:
    ws = FakeSocket([])
    relay = connection.SpanRelay()

    async def relay_one() -> None:
        relay.bind(asyncio.get_running_loop(), ws)  # type: ignore[arg-type]
        assert relay.send("c3Bhbg==") is True
        # Fire-and-forget onto the loop: yield so the scheduled send runs.
        await asyncio.sleep(0)

    asyncio.run(relay_one())

    message = workbench_ws_message_adapter.validate_json(ws.sent[0])
    assert message.id is None
    assert message.frame == SpanFrame(payload="c3Bhbg==")


def test_pump_preserves_trace_context_without_leaking_to_caller():
    from repo2ree_telemetry.spans import attach_remote_context, current_traceparent, detach_context

    parent = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    token = attach_remote_context(parent)
    observed = []

    def generate():
        observed.append(current_traceparent())
        yield from ()

    async def send(frame):
        pytest.fail("empty generator must not send")

    try:
        asyncio.run(connection._pump(send, generate))
        assert observed == [parent]
        assert current_traceparent() == parent
    finally:
        detach_context(token)
