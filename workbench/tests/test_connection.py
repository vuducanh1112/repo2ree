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

import repo2ree_workbench.connection as connection
from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import COPY_CHUNK_BYTES, ResultFrame
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import (
    AssignAllocationRequest,
    CancelRequest,
    CancelRunRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    WorkbenchWsRequest,
    workbench_hello_adapter,
    workbench_ws_message_adapter,
)
from repo2ree_workbench.connection import _serve, run_workbench
from repo2ree_workbench.service import WorkbenchService


class FakeSocket:
    """Yields queued inbound messages; captures what the workbench sends back."""

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


class FakeExec:
    query_result: bytes = b""
    canceled_runs: ClassVar[list[str]] = []

    def __init__(self) -> None:
        # Assignment refuses a workbench whose root already holds an REE, so
        # every fake backend gets its own empty root.
        self._root = tempfile.TemporaryDirectory()
        self.root = Path(self._root.name)

    def exec_query_stream(self, argv: list[str], timeout: int = 30):
        for offset in range(0, len(self.query_result), COPY_CHUNK_BYTES):
            yield self.query_result[offset : offset + COPY_CHUNK_BYTES]

    def exec_simple(self, argv: list[str], timeout: int = 60) -> None:
        return None

    def cancel_run(self, run_id: str) -> None:
        self.canceled_runs.append(run_id)


def _allocation() -> AllocationRequest:
    return AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        profile_id="standard",
        profile_revision="1",
    )


def _service(exec_backend: object | None = None) -> WorkbenchService:
    """A workbench already bound to its allocation, as the control plane leaves it."""
    service = WorkbenchService(exec_backend or FakeExec())  # type: ignore[arg-type]
    service.assign(_allocation())
    return service


def _unassigned_service() -> WorkbenchService:
    return WorkbenchService(FakeExec())  # type: ignore[arg-type]


async def _serve_and_settle(ws: FakeSocket) -> None:
    await asyncio.wait_for(_serve(ws, _service()), timeout=10.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [workbench_ws_message_adapter.validate_json(text) for text in ws.sent]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    ws = FakeSocket(
        [
            "this is not json",
            WorkbenchWsRequest(id="r1", request=CancelRunRequest(run_id="run-1")).model_dump_json(),
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
            WorkbenchWsRequest(id="r2", request=CancelRunRequest(run_id="run-2")).model_dump_json(),
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
        req = WorkbenchWsRequest(id="r1", request=ExecQueryRequest(argv=["build-archive"]))
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
    ws = FakeSocket([WorkbenchWsRequest(id="c1", request=CancelRunRequest(run_id="run-7")).model_dump_json()])
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
        def exec_query_stream(self, argv: list[str], timeout: int = 30):
            release.wait(0.5)
            yield b"too late"

    ws = FakeSocket(
        [
            WorkbenchWsRequest(id="r1", request=ExecQueryRequest(argv=["build-archive"])).model_dump_json(),
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
        def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str]):
            yield ResultFrame(result=ActionResult.failed("execution", "command failed", origin="workbench"))

    request = ExecActionRequest(cmd_json="{}", run_id="run-1")
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
    monkeypatch.setattr(connection, "_connected_gauge", ConnectedGauge())

    opaque_enrollment = "test-enrollment-value"
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_workbench(
                "ws://control/workbench/connect",
                _service(),
                "workbench-1",
                allocation_id="alloc-1",
                enrollment_token=opaque_enrollment,
                location_id="lab-1",
                profile_id="standard",
                profile_revision="1",
            )
        )

    hello = workbench_hello_adapter.validate_json(ws.sent[0])
    assert hello.workbench_id == "workbench-1"
    assert hello.allocation_id == "alloc-1"
    assert hello.enrollment_token == opaque_enrollment
    assert (hello.location_id, hello.profile_id, hello.profile_revision) == ("lab-1", "standard", "1")
    assert hello.nonce
    assert connected_values == [1, -1]


def test_execution_before_assignment_answers_an_error_frame() -> None:
    # The bind is the workbench's own gate: an unassigned bench answers the
    # control plane rather than running anything against an unclaimed root.
    ws = FakeSocket([WorkbenchWsRequest(id="r1", request=ExecSimpleRequest(argv=["doctor"])).model_dump_json()])
    asyncio.run(asyncio.wait_for(_serve(ws, _unassigned_service()), timeout=2.0))  # type: ignore[arg-type]

    message = _frames(ws)[-1]
    assert message.frame.type == "error"
    assert "assigned" in message.frame.detail


def test_assignment_binds_the_workbench_and_is_idempotent() -> None:
    # ``ensure`` may be retried, so the same allocation may be assigned twice;
    # only a *different* allocation is a mismatched bind worth refusing.
    ws = FakeSocket(
        [
            WorkbenchWsRequest(id="a1", request=AssignAllocationRequest(allocation=_allocation())).model_dump_json(),
            WorkbenchWsRequest(id="a2", request=AssignAllocationRequest(allocation=_allocation())).model_dump_json(),
            WorkbenchWsRequest(id="r1", request=ExecSimpleRequest(argv=["doctor"])).model_dump_json(),
        ]
    )
    asyncio.run(asyncio.wait_for(_serve(ws, _unassigned_service()), timeout=2.0))  # type: ignore[arg-type]

    assert [(m.id, m.frame.type) for m in _frames(ws)] == [("a1", "done"), ("a2", "done"), ("r1", "done")]


def test_a_second_allocation_cannot_rebind_a_bound_workbench() -> None:
    other = _allocation().model_copy(update={"allocation_id": "alloc-2", "ree_id": "ree-2"})
    ws = FakeSocket([WorkbenchWsRequest(id="a1", request=AssignAllocationRequest(allocation=other)).model_dump_json()])
    asyncio.run(asyncio.wait_for(_serve(ws, _service()), timeout=2.0))  # type: ignore[arg-type]

    message = _frames(ws)[-1]
    assert message.frame.type == "error"
    assert "already assigned" in message.frame.detail
