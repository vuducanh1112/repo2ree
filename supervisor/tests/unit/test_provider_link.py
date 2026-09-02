from __future__ import annotations

import threading

from repo2ree_protocol import (
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    EnsureAllocationRequest,
    FixedResources,
    Frame,
    ProviderHello,
    ProviderWsMessage,
    ProviderWsRequest,
    RequiredCapabilities,
    SubstrateKind,
    WorkbenchProfile,
)
from repo2ree_supervisor.provider_link import ProviderConnection, ProviderConnectionRegistry, WsProviderClient


def _profile() -> WorkbenchProfile:
    return WorkbenchProfile(
        id="standard",
        revision="1",
        location_id="lab-1",
        label="Standard",
        required=RequiredCapabilities(
            substrate=SubstrateKind.DOCKER_NESTED,
            resources=FixedResources(),
        ),
    )


def test_provider_client_resolves_exact_location_profile_and_sends_identity_only() -> None:
    sent: list[str] = []
    dispatched = threading.Event()

    def record(text: str) -> None:
        sent.append(text)
        dispatched.set()

    registry = ProviderConnectionRegistry()
    connection = ProviderConnection(
        record,
        ProviderHello(
            provider_id="provider-1",
            location_id="lab-1",
            location_label="Lab 1",
            profiles=(_profile(),),
        ),
    )
    registry.register("provider-1", connection)
    client = WsProviderClient(registry)
    provider_id, profile = client.resolve_profile("lab-1", "standard")
    allocation = AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        profile_id="standard",
        profile_revision="1",
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

    assert profile == _profile()
    status = received[0]
    assert isinstance(status, AllocationStatusFrame)
    assert status.allocation_id == "alloc-1"
    assert "image" not in sent[0]
