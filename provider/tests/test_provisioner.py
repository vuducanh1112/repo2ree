from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_protocol import AllocationRequest, DoneFrame, Frame
from repo2ree_provider_docker.provisioner import ProvisionerService


class _Backend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def ensure(
        self,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
        image: str,
    ) -> Iterator[Frame]:
        self.calls.append(("ensure", image))
        yield DoneFrame()

    def release(self, allocation_id: str) -> None:
        self.calls.append(("release", allocation_id))

    def inspect(self, allocation_id: str) -> bool:
        self.calls.append(("inspect", allocation_id))
        return True


def _allocation(profile_id: str = "standard") -> AllocationRequest:
    return AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        profile_id=profile_id,
        profile_revision="1",
    )


def test_provider_resolves_profile_to_private_image() -> None:
    backend = _Backend()
    provisioner = ProvisionerService(backend, {("standard", "1"): "private/image@sha256:123"})

    assert list(provisioner.ensure(_allocation(), "wb-1", "token")) == [DoneFrame()]
    assert backend.calls == [("ensure", "private/image@sha256:123")]


def test_provider_rejects_unknown_profile_without_fallback() -> None:
    provisioner = ProvisionerService(_Backend(), {("standard", "1"): "private/image@sha256:123"})

    with pytest.raises(ValueError, match="unsupported workbench profile"):
        list(provisioner.ensure(_allocation("unknown"), "wb-1", "token"))


def test_inspect_and_release_are_keyed_by_allocation_id() -> None:
    backend = _Backend()
    provisioner = ProvisionerService(backend, {})

    assert provisioner.inspect("alloc-1") is True
    provisioner.release("alloc-1")

    assert backend.calls == [("inspect", "alloc-1"), ("release", "alloc-1")]
