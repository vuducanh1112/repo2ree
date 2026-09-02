"""The capacity connection's request-serving loop, driven by a fake socket.

Exercises ``_serve`` directly: the fake yields inbound messages like a real
``async for ws`` would and captures outbound sends, so dispatch and its failure
modes are tested without a network or a Docker daemon.

The property this file is really guarding is that a provider answers *every*
request it can name — a capacity call that produces no terminal frame strands
the control plane until its frame-gap timeout, with an allocation half-created
on this host.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import pytest

import repo2ree_provider_docker.connection as connection
from repo2ree_protocol.frames import DoneFrame, Frame, LogFrame, WorkbenchRef, WorkbenchRefFrame
from repo2ree_protocol.provider import (
    DockerWorkbenchSpec,
    IsRunningRequest,
    ProviderCancelRequest,
    ProviderWsRequest,
    ProvisionRequest,
    RemoveRequest,
    provider_hello_adapter,
    provider_ws_message_adapter,
)
from repo2ree_provider_docker.connection import _serve, run_provider
from repo2ree_provider_docker.provisioner import ProvisionerService

_REF = WorkbenchRef(runtime="docker", token="opaque-handle")  # noqa: S106 - an opaque backend handle, not a secret
_ENROLLMENT = "test-enrollment-value"


class FakeSocket:
    """Yields queued inbound messages; captures what the provider sends back."""

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


class FakeBackend:
    """An isolation backend that records calls instead of touching Docker."""

    runtime_name = "docker"

    def __init__(self, *, running: bool = True) -> None:
        self.calls: list[str] = []
        self.running = running
        self.fail_with: Exception | None = None
        self.block: threading.Event | None = None

    def provision(
        self,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: DockerWorkbenchSpec,
    ) -> Iterator[Frame]:
        self.calls.append("provision")
        if self.block is not None:
            self.block.wait(0.5)
        if self.fail_with is not None:
            raise self.fail_with
        yield LogFrame(stream="stdout", level="info", message=f"creating bench for {ree_id}")
        yield WorkbenchRefFrame(ref=_REF)

    def remove(self, ref: WorkbenchRef) -> None:
        self.calls.append("remove")
        if self.fail_with is not None:
            raise self.fail_with

    def is_running(self, ref: WorkbenchRef) -> bool:
        self.calls.append("is_running")
        return self.running


def _provisioner(backend: FakeBackend) -> ProvisionerService:
    return ProvisionerService({backend.runtime_name: backend})


async def _serve_and_settle(ws: FakeSocket, backend: FakeBackend) -> None:
    await asyncio.wait_for(_serve(ws, _provisioner(backend)), timeout=10.0)  # type: ignore[arg-type]


def _frames(ws: FakeSocket) -> list[Any]:
    return [provider_ws_message_adapter.validate_json(text) for text in ws.sent]


def _provision_request(req_id: str = "r1") -> str:
    return ProviderWsRequest(
        id=req_id,
        request=ProvisionRequest(
            allocation_id="alloc-1",
            workbench_id="wb-1",
            enrollment_token=_ENROLLMENT,
            ree_id="ree-1",
            spec=DockerWorkbenchSpec(base_image="docker:dind"),
        ),
    ).model_dump_json()


def test_provision_streams_its_frames_and_ends_with_a_reference() -> None:
    backend = FakeBackend()
    ws = FakeSocket([_provision_request()])

    asyncio.run(_serve_and_settle(ws, backend))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["r1", "r1"]
    assert [m.frame.type for m in messages] == ["log", "workbench_ref"]
    # The reference is minted by the backend and travels back verbatim; the
    # control plane never learns what is inside its token.
    assert messages[-1].frame.ref == _REF
    assert backend.calls == ["provision"]


def test_is_running_and_remove_answer_their_own_frames() -> None:
    backend = FakeBackend(running=False)
    ws = FakeSocket(
        [
            ProviderWsRequest(id="r1", request=IsRunningRequest(ref=_REF)).model_dump_json(),
            ProviderWsRequest(id="r2", request=RemoveRequest(ref=_REF)).model_dump_json(),
        ]
    )

    asyncio.run(_serve_and_settle(ws, backend))

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["r1"].type == "running"
    assert by_id["r1"].running is False
    assert by_id["r2"].type == "done"
    assert backend.calls == ["is_running", "remove"]


def test_malformed_request_is_dropped_and_serving_continues() -> None:
    backend = FakeBackend()
    ws = FakeSocket(
        [
            "this is not json",
            ProviderWsRequest(id="r1", request=IsRunningRequest(ref=_REF)).model_dump_json(),
        ]
    )

    asyncio.run(_serve_and_settle(ws, backend))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["r1"]
    assert messages[0].frame.type == "running"


def test_unknown_op_answers_error_frame() -> None:
    # An op this provider does not know (a version-skewed control plane) fails
    # the envelope's discriminated union; the id is still recoverable, so the
    # caller gets an error frame instead of hanging until its frame-gap timeout.
    backend = FakeBackend()
    ws = FakeSocket(['{"id": "r1", "request": {"op": "frobnicate"}}'])

    asyncio.run(_serve_and_settle(ws, backend))

    messages = _frames(ws)
    assert messages[0].id == "r1"
    assert messages[0].frame.type == "error"
    assert "frobnicate" in messages[0].frame.detail


def test_backend_failure_becomes_a_terminal_error_frame() -> None:
    # A half-created allocation must still terminate its stream: the control
    # plane's provision path only removes what it was told about.
    backend = FakeBackend()
    backend.fail_with = RuntimeError("docker daemon unreachable")
    ws = FakeSocket([_provision_request()])

    asyncio.run(_serve_and_settle(ws, backend))

    terminal = _frames(ws)[-1]
    assert terminal.frame.type == "error"
    assert "docker daemon unreachable" in terminal.frame.detail


def test_cancel_for_unknown_request_still_answers_done() -> None:
    # Cancel is idempotent: the target may have finished (or never existed) by
    # the time it arrives, and the canceller still deserves an answer.
    backend = FakeBackend()
    ws = FakeSocket([ProviderWsRequest(id="c1", request=ProviderCancelRequest(request_id="nope")).model_dump_json()])

    asyncio.run(_serve_and_settle(ws, backend))

    messages = _frames(ws)
    assert [m.id for m in messages] == ["c1"]
    assert messages[0].frame.type == "done"


def test_cancel_stops_an_inflight_provision() -> None:
    # An abandoned capacity request stops working and ships no frames; only the
    # cancel itself is answered. The backend blocks so the provision is still in
    # flight when the cancel lands.
    backend = FakeBackend()
    backend.block = threading.Event()
    ws = FakeSocket(
        [
            _provision_request(),
            ProviderWsRequest(id="c1", request=ProviderCancelRequest(request_id="r1")).model_dump_json(),
        ]
    )

    try:
        asyncio.run(asyncio.wait_for(_serve(ws, _provisioner(backend)), timeout=2.0))  # type: ignore[arg-type]
    finally:
        backend.block.set()

    by_id = {m.id: m.frame for m in _frames(ws)}
    assert by_id["c1"].type == "done"
    assert "r1" not in by_id


def test_hello_announces_identity_and_substrate_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = FakeSocket([])
    connects = 0

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

    monkeypatch.setattr(connection, "connect", connect_once)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_provider(
                "ws://control/provider/connect",
                _provisioner(FakeBackend()),
                "docker-provider-1",
                docker_mode="host-socket",
                reconnect_delay=0.0,
            )
        )

    hello = provider_hello_adapter.validate_json(ws.sent[0])
    assert hello.provider_id == "docker-provider-1"
    assert hello.provider_kind == "docker"
    assert hello.docker_mode == "host-socket"
    # A per-process nonce is what tells a reconnect apart from a second instance
    # claiming the same persisted provider id.
    assert hello.nonce


def test_a_lost_connection_is_retried_with_the_same_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    sockets: list[FakeSocket] = []
    attempts = 0

    class ConnectionContext:
        async def __aenter__(self) -> FakeSocket:
            ws = FakeSocket([])
            sockets.append(ws)
            return ws

        async def __aexit__(self, *args: object) -> None:
            return None

    def connect_flaky(url: str) -> ConnectionContext:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("connection refused")
        if attempts > 2:
            raise asyncio.CancelledError
        return ConnectionContext()

    monkeypatch.setattr(connection, "connect", connect_flaky)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_provider(
                "ws://control/provider/connect",
                _provisioner(FakeBackend()),
                "docker-provider-1",
                reconnect_delay=0.0,
            )
        )

    assert attempts == 3
    assert [provider_hello_adapter.validate_json(ws.sent[0]).provider_id for ws in sockets] == ["docker-provider-1"]


def test_provision_frames_survive_a_backend_slower_than_the_stream_buffer() -> None:
    # The producer runs in a worker thread behind a bounded memory stream; a
    # backend that emits more frames than the buffer holds must not lose any.
    class ChattyBackend(FakeBackend):
        def provision(
            self,
            allocation_id: str,
            workbench_id: str,
            enrollment_token: str,
            ree_id: str,
            spec: DockerWorkbenchSpec,
        ) -> Iterator[Frame]:
            self.calls.append("provision")
            for index in range(32):
                yield LogFrame(stream="stdout", level="info", message=f"step {index}")
            yield DoneFrame()

    backend = ChattyBackend()
    ws = FakeSocket([_provision_request()])

    asyncio.run(_serve_and_settle(ws, backend))

    frames = [m.frame for m in _frames(ws)]
    assert [f.type for f in frames] == ["log"] * 32 + ["done"]
    assert [f.message for f in frames[:32]] == [f"step {index}" for index in range(32)]
