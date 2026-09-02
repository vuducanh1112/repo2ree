from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

from repo2ree_protocol import (
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    DoneFrame,
    EnsureAllocationRequest,
    Frame,
    InspectAllocationRequest,
    ProviderWsRequest,
    ReleaseAllocationRequest,
)
from repo2ree_protocol.provider import provider_ws_message_adapter
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
        image: str,
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
        profile_id="standard",
        profile_revision="1",
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
    provisioner = ProvisionerService(FakeBackend(), {("standard", "1"): "private:image"})

    asyncio.run(_serve(socket, provisioner))  # type: ignore[arg-type]

    by_id = {message.id: message.frame for message in _messages(socket)}
    assert by_id["ensure"].type == "allocation_status"
    assert by_id["inspect"].type == "allocation_status"
    assert by_id["inspect"].state == AllocationState.LOST
    assert by_id["release"] == DoneFrame()


def test_unknown_operation_returns_a_terminal_error() -> None:
    socket = FakeSocket(['{"id":"bad","request":{"op":"schedule_best_machine"}}'])

    asyncio.run(_serve(socket, ProvisionerService(FakeBackend(), {})))  # type: ignore[arg-type]

    assert _messages(socket)[0].frame.type == "error"
