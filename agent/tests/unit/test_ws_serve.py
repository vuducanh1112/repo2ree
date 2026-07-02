"""The agent's request-serving loop, driven by a fake socket.

Exercises ``_serve`` directly: the fake yields inbound messages like a real
``async for ws`` would and captures outbound sends, so dispatch and its
failure modes are tested without a network or a Docker daemon.
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from repo2ree_agent.ws_client import _serve
from repo2ree_protocol.agent import WsRequest, ws_message_adapter


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

    def is_running(self, container_name: str) -> bool:
        return container_name == "wb-up"

    def exec_query(self, container_name: str, argv: list[str], timeout: int = 30) -> bytes:
        return self.query_result


async def _serve_and_settle(ws: FakeSocket) -> None:
    await asyncio.wait_for(_serve(ws, FakeRuntime()), timeout=2.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [ws_message_adapter.validate_json(text) for text in ws.sent]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    ws = FakeSocket(
        [
            "this is not json",
            WsRequest(id="r1", op="is_running", args={"container_name": "wb-up"}).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["r1"]
    assert messages[0].frame.type == "running"
    assert messages[0].frame.running is True


def test_unknown_op_answers_error_frame() -> None:
    ws = FakeSocket([WsRequest(id="r1", op="frobnicate", args={}).model_dump_json()])
    asyncio.run(_serve_and_settle(ws))

    messages = _frames(ws)
    assert messages[0].frame.type == "error"
    assert "frobnicate" in messages[0].frame.detail


def test_invalid_args_answer_error_frame_without_killing_connection() -> None:
    ws = FakeSocket(
        [
            WsRequest(id="r1", op="is_running", args={"wrong_field": "x"}).model_dump_json(),
            WsRequest(id="r2", op="is_running", args={"container_name": "wb-down"}).model_dump_json(),
        ]
    )
    asyncio.run(_serve_and_settle(ws))

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["r1"].type == "error"
    assert by_id["r2"].type == "running"
    assert by_id["r2"].running is False


def test_exec_query_result_is_chunked_under_the_frame_cap() -> None:
    # A large query result (a sealed archive) must never ride one frame: the
    # agent slices it into COPY_CHUNK_BYTES chunks and ends with ``done``.
    payload = bytes(range(256)) * 4 * 1024  # 1 MiB, above one chunk
    FakeRuntime.query_result = payload
    try:
        req = WsRequest(id="r1", op="exec_query", args={"container_name": "wb", "argv": ["build-archive"]})
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
