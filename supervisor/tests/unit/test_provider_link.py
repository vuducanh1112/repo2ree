from __future__ import annotations

import threading
from collections.abc import Callable

import pytest

from repo2ree_protocol import (
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    EnsureAllocationRequest,
    Frame,
    ProviderHello,
    ProviderWsMessage,
    ProviderWsRequest,
    WorkbenchImage,
)
from repo2ree_supervisor.client import WorkbenchUnavailableError
from repo2ree_supervisor.provider_link import ProviderConnection, ProviderConnectionRegistry, WsProviderClient

_IMAGE = "docker.io/library/docker:29-dind"


def _registry(
    *,
    accepts_custom_image: bool = False,
    send: Callable[[str], None] = lambda _text: None,
) -> tuple[ProviderConnectionRegistry, ProviderConnection]:
    registry = ProviderConnectionRegistry()
    connection = ProviderConnection(
        send,
        ProviderHello(
            provider_id="provider-1",
            location_id="lab-1",
            location_label="Lab 1",
            images=(WorkbenchImage(ref=_IMAGE, id="standard", label="Standard"),),
            accepts_custom_image=accepts_custom_image,
        ),
    )
    registry.register("provider-1", connection)
    return registry, connection


def test_blank_image_resolves_to_the_locations_first_catalog_entry() -> None:
    registry, _connection = _registry()

    assert WsProviderClient(registry).resolve_location("lab-1", "") == ("provider-1", _IMAGE)


def test_a_ref_the_location_did_not_publish_is_refused_unless_it_accepts_one() -> None:
    strict, _connection = _registry()
    with pytest.raises(WorkbenchUnavailableError, match="refuses custom images"):
        WsProviderClient(strict).resolve_location("lab-1", "ghcr.io/me/bench:v3")

    permissive, _connection = _registry(accepts_custom_image=True)
    assert WsProviderClient(permissive).resolve_location("lab-1", "ghcr.io/me/bench:v3") == (
        "provider-1",
        "ghcr.io/me/bench:v3",
    )


def test_provider_client_sends_the_resolved_image_and_no_capability_vocabulary() -> None:
    sent: list[str] = []
    dispatched = threading.Event()

    def record(text: str) -> None:
        sent.append(text)
        dispatched.set()

    registry, connection = _registry(send=record)
    client = WsProviderClient(registry)
    provider_id, image = client.resolve_location("lab-1", _IMAGE)
    allocation = AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        image=image,
    )

    # The reply stream is lazy, so it is drained on a second thread: the request
    # only reaches the wire once someone pulls the first frame.
    reply = client.ensure(provider_id, allocation, "wb-1", "token")
    received: list[Frame] = []
    consumer = threading.Thread(target=lambda: received.append(next(iter(reply))))
    consumer.start()
    assert dispatched.wait(2.0), "ensure did not send a capacity request"

    envelope = ProviderWsRequest.model_validate_json(sent[0])
    assert isinstance(envelope.request, EnsureAllocationRequest)
    connection.on_message(
        ProviderWsMessage(
            id=envelope.id,
            frame=AllocationStatusFrame(
                allocation_id="alloc-1",
                state=AllocationState.WAITING_FOR_WORKBENCH,
            ),
        ).model_dump_json()
    )
    consumer.join(timeout=2.0)
    assert not consumer.is_alive(), "the reply stream did not deliver its first frame"

    assert image == _IMAGE
    status = received[0]
    assert isinstance(status, AllocationStatusFrame)
    assert status.allocation_id == "alloc-1"
    # The image goes down the wire, because the provider has to run it. Nothing
    # describing what it supplies does.
    assert _IMAGE in sent[0]
    for word in ("substrate", "capabilit", "required", "software"):
        assert word not in sent[0]
