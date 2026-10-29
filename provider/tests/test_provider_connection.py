from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from repo2ree_protocol.allocation import AllocationRequest, AllocationState
from repo2ree_protocol.frames import AllocationStatusFrame, DoneFrame, Frame
from repo2ree_protocol.provider import (
    EnsureAllocationRequest,
    InspectAllocationRequest,
    ProviderWsRequest,
    ReleaseAllocationRequest,
    provider_ws_message_adapter,
)
from repo2ree_provider_docker import connection
from repo2ree_provider_docker.connection import _serve
from repo2ree_provider_docker.provisioner import ProvisionerService


class FakeSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.sent: list[str] = []

    def __aiter__(self) -> FakeSocket:
        return self

    async def __anext__(self) -> str:
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)

    async def send(self, text: str) -> None:
        self.sent.append(text)


class FakeBackend:
    def ensure(
        self,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        yield AllocationStatusFrame(
            allocation_id=allocation.allocation_id,
            state=AllocationState.WAITING_FOR_WORKBENCH,
            workbench_id=workbench_id,
        )

    def inspect(self, allocation_id: str) -> bool:
        return False

    def release(self, allocation_id: str) -> None:
        return None


def _allocation() -> AllocationRequest:
    return AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        image="docker.io/library/docker:29-dind",
    )


def _messages(socket: FakeSocket) -> list[Any]:
    return [provider_ws_message_adapter.validate_json(text) for text in socket.sent]


def test_capacity_connection_serves_ensure_inspect_and_release() -> None:
    socket = FakeSocket(
        [
            ProviderWsRequest(
                id="ensure",
                request=EnsureAllocationRequest(
                    allocation=_allocation(),
                    workbench_id="wb-1",
                    enrollment_token="test-enrollment-value",  # noqa: S106
                ),
            ).model_dump_json(),
            ProviderWsRequest(
                id="inspect", request=InspectAllocationRequest(allocation_id="alloc-1")
            ).model_dump_json(),
            ProviderWsRequest(
                id="release", request=ReleaseAllocationRequest(allocation_id="alloc-1")
            ).model_dump_json(),
        ]
    )
    provisioner = ProvisionerService(FakeBackend(), catalog={"curated:image"}, accepts_custom_image=True)

    asyncio.run(_serve(socket, provisioner))  # type: ignore[arg-type]

    by_id = {message.id: message.frame for message in _messages(socket)}
    assert by_id["ensure"].type == "allocation_status"
    assert by_id["inspect"].type == "allocation_status"
    assert by_id["inspect"].state == AllocationState.LOST
    assert by_id["release"] == DoneFrame()


def test_unknown_operation_returns_a_terminal_error() -> None:
    socket = FakeSocket(['{"id":"bad","request":{"op":"schedule_best_machine"}}'])

    provisioner = ProvisionerService(FakeBackend(), catalog=set(), accepts_custom_image=True)
    asyncio.run(_serve(socket, provisioner))  # type: ignore[arg-type]

    assert _messages(socket)[0].frame.type == "error"


def test_a_provider_request_joins_the_supervisors_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker calls made for a request nest under it, and it under the supervisor's dispatching span."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer(__name__)
    monkeypatch.setattr(connection, "tracer", test_tracer)

    class TracedBackend(FakeBackend):
        def ensure(self, allocation: AllocationRequest, workbench_id: str, enrollment_token: str) -> Iterator[Frame]:
            # What repo2ree_docker does for every CLI call: a span against the current context.
            test_tracer.start_span("docker.pull").end()
            yield from super().ensure(allocation, workbench_id, enrollment_token)

    supervisor = "00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01"
    socket = FakeSocket(
        [
            ProviderWsRequest(
                id="ensure",
                request=EnsureAllocationRequest(
                    allocation=_allocation(),
                    workbench_id="wb-1",
                    enrollment_token="test-enrollment-value",  # noqa: S106
                ),
                traceparent=supervisor,
            ).model_dump_json()
        ]
    )
    provisioner = ProvisionerService(TracedBackend(), catalog={"curated:image"}, accepts_custom_image=True)
    asyncio.run(_serve(socket, provisioner))  # type: ignore[arg-type]
    provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    request, pull = spans["provider.request"], spans["docker.pull"]
    assert f"{request.context.trace_id:032x}" == "c" * 32
    assert request.parent is not None
    assert f"{request.parent.span_id:016x}" == "d" * 16
    assert pull.context.trace_id == request.context.trace_id
    assert pull.parent is not None
    assert pull.parent.span_id == request.context.span_id
    assert request.attributes is not None
    assert request.attributes["repo2ree.allocation_id"] == "alloc-1"
    assert request.attributes["repo2ree.workbench_id"] == "wb-1"
