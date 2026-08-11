"""The control connection's request-serving loop, driven by a fake socket.

Exercises ``_serve`` directly: the fake yields inbound messages like a real
``async for ws`` would and captures outbound sends, so dispatch and its
failure modes are tested without a network or a Docker daemon.
"""

from __future__ import annotations

import asyncio
import base64
import threading
from typing import Any, ClassVar

import pytest

import repo2ree_agent.control.connection as connection
from repo2ree_agent.control.connection import _serve, run_agent
from repo2ree_agent.runtimes.base import WorkbenchGoneError
from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.agent import (
    COPY_CHUNK_BYTES,
    AgentRequest,
    CancelRequest,
    CancelRunRequest,
    DockerWorkbenchSpec,
    ErrorFrame,
    ExecActionRequest,
    ExecQueryRequest,
    IsRunningRequest,
    ProvisionRequest,
    ResultFrame,
    WorkbenchRef,
    WsRequest,
    ws_hello_adapter,
    ws_message_adapter,
)
from repo2ree_protocol.result import ActionResult


def _ref(container_name: str) -> WorkbenchRef:
    return WorkbenchRef(runtime="docker", token=container_name)


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
    canceled_runs: ClassVar[list[tuple[str, str]]] = []

    def is_running(self, ref: WorkbenchRef) -> bool:
        return ref.token == "wb-up"  # noqa: S105 - opaque reference, not a credential

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30):
        for offset in range(0, len(self.query_result), COPY_CHUNK_BYTES):
            yield self.query_result[offset : offset + COPY_CHUNK_BYTES]

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None:
        self.canceled_runs.append((ref.token, run_id))


async def _serve_and_settle(ws: FakeSocket) -> None:
    service = WorkbenchService({"docker": FakeRuntime()})  # type: ignore[dict-item]
    await asyncio.wait_for(_serve(ws, service), timeout=2.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [ws_message_adapter.validate_json(text) for text in ws.sent]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    ws = FakeSocket(
        [
            "this is not json",
            WsRequest(id="r1", request=IsRunningRequest(ref=_ref("wb-up"))).model_dump_json(),
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
            WsRequest(id="r2", request=IsRunningRequest(ref=_ref("wb-down"))).model_dump_json(),
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
        req = WsRequest(id="r1", request=ExecQueryRequest(ref=_ref("wb"), argv=["build-archive"]))
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
    ws = FakeSocket([WsRequest(id="c1", request=CancelRunRequest(ref=_ref("wb"), run_id="run-7")).model_dump_json()])
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
        def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30):
            release.wait(0.5)
            yield b"too late"

    ws = FakeSocket(
        [
            WsRequest(id="r1", request=ExecQueryRequest(ref=_ref("wb"), argv=["build-archive"])).model_dump_json(),
            WsRequest(id="c1", request=CancelRequest(request_id="r1")).model_dump_json(),
        ]
    )
    try:
        service = WorkbenchService({"docker": BlockingRuntime()})  # type: ignore[dict-item]
        asyncio.run(asyncio.wait_for(_serve(ws, service), timeout=2.0))  # type: ignore[arg-type]
    finally:
        release.set()

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["c1"].type == "done"
    assert "r1" not in by_id


@pytest.mark.parametrize(
    ("runtime_type", "expected_frame", "expected_status"),
    [
        ("error", "error", "failed"),
        ("gone", "unavailable", "unavailable"),
        ("failed_result", "result", "failed"),
    ],
)
def test_stream_terminal_frame_drives_request_telemetry(
    runtime_type: str,
    expected_frame: str,
    expected_status: str,
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

    class TerminalRuntime(FakeRuntime):
        def provision(self, ree_id: str, spec: DockerWorkbenchSpec):
            if runtime_type == "gone":
                raise WorkbenchGoneError("bench disappeared")
            yield ErrorFrame(detail="pull failed")

        def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]):
            yield ResultFrame(result=ActionResult.failed("execution", "command failed", origin="agent"))

    if runtime_type == "failed_result":
        request: AgentRequest = ExecActionRequest(ref=_ref("wb"), cmd_json="{}", run_id="run-1")
    else:
        request = ProvisionRequest(ree_id="ree-1", spec=DockerWorkbenchSpec(base_image="ubuntu:24.04"))
    ws = FakeSocket([WsRequest(id="r1", request=request).model_dump_json()])
    service = WorkbenchService({"docker": TerminalRuntime()})  # type: ignore[dict-item]

    with caplog.at_level("WARNING", logger=connection.__name__):
        asyncio.run(asyncio.wait_for(_serve(ws, service), timeout=2.0))  # type: ignore[arg-type]

    assert _frames(ws)[-1].frame.type == expected_frame
    assert statuses == [expected_status]
    assert [value for value, _ in active] == [1, -1]
    assert durations[-1]["repo2ree.status"] == expected_status
    assert durations[-1]["repo2ree.workbench.runtime"] == "docker"
    assert expected_status in caplog.text
    if runtime_type == "failed_result":
        assert failures[-1] is not None
        assert exit_codes[-1] == 1
    else:
        assert failures[-1] is None
        assert exit_codes[-1] is None


def test_connection_hello_and_connected_gauge_are_balanced(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = FakeSocket([])
    connects = 0
    connected_values: list[int] = []

    class ConnectionContext:
        async def __aenter__(self) -> FakeSocket:
            return ws

        async def __aexit__(self, *args: object) -> None:
            return None

    def connect_once(url: str) -> ConnectionContext:
        nonlocal connects
        connects += 1
        if connects > 1:
            raise asyncio.CancelledError
        return ConnectionContext()

    class ConnectedGauge:
        def add(self, value: int, attrs: dict[str, str]) -> None:
            connected_values.append(value)

    monkeypatch.setattr(connection, "connect", connect_once)
    monkeypatch.setattr(connection, "_connected_agents", ConnectedGauge())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_agent("ws://control/agent/connect", WorkbenchService({}), "agent-1", docker_mode="dind"))

    hello = ws_hello_adapter.validate_json(ws.sent[0])
    assert hello.agent_id == "agent-1"
    assert hello.docker_mode == "dind"
    assert hello.nonce
    assert connected_values == [1, -1]
