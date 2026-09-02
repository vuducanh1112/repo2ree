"""Capacity-only provider WebSocket client behaviour."""

from __future__ import annotations

import threading

from repo2ree_protocol.frames import WorkbenchRef, WorkbenchRefFrame
from repo2ree_protocol.provider import (
    DockerWorkbenchSpec,
    ProviderWsMessage,
    ProviderWsRequest,
    provider_ws_request_adapter,
)
from repo2ree_supervisor import ProviderConnection, ProviderConnectionRegistry, WsProviderClient


def test_provider_client_sends_allocation_identity_and_selected_image() -> None:
    sent: list[ProviderWsRequest] = []
    sent_event = threading.Event()

    def capture(text: str) -> None:
        sent.append(provider_ws_request_adapter.validate_json(text))
        sent_event.set()

    connection = ProviderConnection(capture)
    registry = ProviderConnectionRegistry()
    registry.register("docker-1", connection)
    client = WsProviderClient(registry)
    frames: list[object] = []

    def provision() -> None:
        frames.extend(
            client.provision(
                "docker-1",
                "allocation-1",
                "workbench-1",
                "enrollment-token",
                "ree-1",
                DockerWorkbenchSpec(base_image="ubuntu:24.04"),
            )
        )

    thread = threading.Thread(target=provision)
    thread.start()
    assert sent_event.wait(timeout=2)
    request = sent[0]
    assert request.request.op == "provision"
    assert request.request.allocation_id == "allocation-1"
    assert request.request.workbench_id == "workbench-1"
    assert request.request.spec.base_image == "ubuntu:24.04"

    ref = WorkbenchRef(runtime="docker", token="opaque")  # noqa: S106 - opaque runtime reference
    connection.on_message(ProviderWsMessage(id=request.id, frame=WorkbenchRefFrame(ref=ref)).model_dump_json())
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert frames == [WorkbenchRefFrame(ref=ref)]
