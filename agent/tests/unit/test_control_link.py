"""The agent's request-serving loop, driven by a fake socket.

Exercises ``_serve`` directly: the fake yields inbound messages like a real
``async for ws`` would and captures outbound sends, so dispatch and its
failure modes are tested without a network or a Docker daemon.
"""

from __future__ import annotations

import asyncio
import base64
import threading
from typing import Any

from repo2ree_agent.control_link import _serve
from repo2ree_protocol.agent import (
    COPY_CHUNK_BYTES,
    CancelRequest,
    CancelRunRequest,
    ExecQueryRequest,
    IsRunningRequest,
    WsRequest,
    ws_message_adapter,
)


class FakeSocket:
    """Yields queued inbound messages; captures what the agent sends back."""

    def __init__(self, messages: list[str]) -> None:
        self._messages = messages
        self.sent: list[str] = []

    def __aiter__(self) -> FakeSocket:
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, text: str) -> None:
        self.sent.append(text)


class FakeRuntime:
    query_result: bytes = b""
    canceled_runs: list[tuple[str, str]] = []

    def is_running(self, container_name: str) -> bool:
        return container_name == "wb-up"

    def exec_query_stream(self, container_name: str, argv: list[str], timeout: int = 30):
        for offset in range(0, len(self.query_result), COPY_CHUNK_BYTES):
            yield self.query_result[offset : offset + COPY_CHUNK_BYTES]

    def cancel_run(self, container_name: str, run_id: str) -> None:
        self.canceled_runs.append((container_name, run_id))


async def _serve_and_settle(ws: FakeSocket) -> None:
    await asyncio.wait_for(_serve(ws, FakeRuntime()), timeout=2.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [ws_message_adapter.validate_json(text) for text in ws.sent]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    ws = FakeSocket(
        [
            "this is not json",
            WsRequest(id="r1", request=IsRunningRequest(container_name="wb-up")).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["r1"]
    assert messages[0].frame.type == "running"
    assert messages[0].frame.running is True


def test_unknown_op_answers_error_frame() -> None:
    # An op this agent does not know (a version-skewed control plane) fails the
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
            WsRequest(id="r2", request=IsRunningRequest(container_name="wb-down")).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["r1"].type == "error"
    assert by_id["r2"].type == "running"
    assert by_id["r2"].running is False


def test_exec_query_result_is_chunked_under_the_frame_cap() -> None:
    # A large query result (a sealed archive) must never ride one frame: the
    # runtime stream is forwarded as bounded frames and ends with ``done``.
    payload = bytes(range(256)) * 4 * 1024  # 1 MiB, above one chunk
    FakeRuntime.query_result = payload
    try:
        req = WsRequest(id="r1", request=ExecQueryRequest(container_name="wb", argv=["build-archive"]))
        ws = FakeSocket([req.model_dump_json()])
        asyncio.run(_serve_and_settle(ws))
    finally:
        FakeRuntime.query_result = b""

    messages = _frames(ws)
    assert [m.frame.type for m in messages] == ["bytes_chunk"] * 4 + ["done"]
    reassembled = b"".join(base64.b64decode(m.frame.data_b64) for m in messages[:-1])
    assert reassembled == payload
    # No single serialized frame approaches the transport's 1 MiB receive cap.
    assert all(len(text) < 512 * 1024 for text in ws.sent)


def test_cancel_for_unknown_request_still_answers_done() -> None:
    # Cancel is idempotent: the target may have finished (or never existed) by
    # the time it arrives, and the canceller still deserves an answer.
    ws = FakeSocket([WsRequest(id="c1", request=CancelRequest(request_id="nope")).model_dump_json()])
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["c1"]
    assert messages[0].frame.type == "done"


def test_cancel_run_marks_run_in_workbench() -> None:
    FakeRuntime.canceled_runs = []
    ws = FakeSocket(
        [WsRequest(id="c1", request=CancelRunRequest(container_name="wb", run_id="run-7")).model_dump_json()]
    )
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert messages[0].frame.type == "done"
    assert FakeRuntime.canceled_runs == [("wb", "run-7")]


def test_cancel_stops_an_inflight_request() -> None:
    # A cancelled request stops working and ships no frames; only the cancel
    # itself is answered. The runtime call blocks so the request is still
    # in flight when the cancel lands.
    release = threading.Event()

    class BlockingRuntime(FakeRuntime):
        def exec_query_stream(self, container_name: str, argv: list[str], timeout: int = 30):
            release.wait(0.5)
            yield b"too late"

    ws = FakeSocket(
        [
            WsRequest(id="r1", request=ExecQueryRequest(container_name="wb", argv=["build-archive"])).model_dump_json(),
            WsRequest(id="c1", request=CancelRequest(request_id="r1")).model_dump_json(),
        ]
    )
    try:
        asyncio.run(asyncio.wait_for(_serve(ws, BlockingRuntime()), timeout=2.0))  # type: ignore[arg-type]
    finally:
        release.set()

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["c1"].type == "done"
    assert "r1" not in by_id
