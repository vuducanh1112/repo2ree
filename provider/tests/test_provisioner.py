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
    ) -> Iterator[Frame]:
        self.calls.append(("ensure", allocation.image))
        yield DoneFrame()

    def release(self, allocation_id: str) -> None:
        self.calls.append(("release", allocation_id))

    def inspect(self, allocation_id: str) -> bool:
        self.calls.append(("inspect", allocation_id))
        return True


_CATALOG_IMAGE = "curated/image@sha256:123"


def _allocation(image: str = _CATALOG_IMAGE) -> AllocationRequest:
    return AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        image=image,
    )


def test_the_requested_image_is_what_the_backend_runs() -> None:
    backend = _Backend()
    provisioner = ProvisionerService(backend, catalog={_CATALOG_IMAGE}, accepts_custom_image=False)

    assert list(provisioner.ensure(_allocation(), "wb-1", "token")) == [DoneFrame()]
    assert backend.calls == [("ensure", _CATALOG_IMAGE)]


def test_an_off_catalog_ref_is_refused_when_the_provider_curates_strictly() -> None:
    """The control plane checks too, but a stale catalog there must not get past this."""
    provisioner = ProvisionerService(_Backend(), catalog={_CATALOG_IMAGE}, accepts_custom_image=False)

    with pytest.raises(ValueError, match="not in this provider's catalog"):
        list(provisioner.ensure(_allocation("ghcr.io/me/bench:v3"), "wb-1", "token"))


def test_an_off_catalog_ref_runs_where_the_provider_accepts_one() -> None:
    backend = _Backend()
    provisioner = ProvisionerService(backend, catalog={_CATALOG_IMAGE}, accepts_custom_image=True)

    assert list(provisioner.ensure(_allocation("ghcr.io/me/bench:v3"), "wb-1", "token")) == [DoneFrame()]
    assert backend.calls == [("ensure", "ghcr.io/me/bench:v3")]


def test_an_allocation_with_no_image_is_a_bug_not_a_default() -> None:
    provisioner = ProvisionerService(_Backend(), catalog={_CATALOG_IMAGE}, accepts_custom_image=True)

    with pytest.raises(ValueError, match="must name an image"):
        list(provisioner.ensure(_allocation(""), "wb-1", "token"))


def test_inspect_and_release_are_keyed_by_allocation_id() -> None:
    backend = _Backend()
    provisioner = ProvisionerService(backend, catalog=set(), accepts_custom_image=True)

    assert provisioner.inspect("alloc-1") is True
    provisioner.release("alloc-1")

    assert backend.calls == [("inspect", "alloc-1"), ("release", "alloc-1")]
