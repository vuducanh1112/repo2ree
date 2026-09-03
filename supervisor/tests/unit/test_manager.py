from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol import (
    ActionResult,
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    Frame,
    ResultFrame,
)
from repo2ree_supervisor import AllocationStore, WorkbenchManager

_CATALOG_IMAGE = "docker.io/library/docker:29-dind"


class FakeProvider:
    def __init__(self, resolved_image: str = "") -> None:
        self.released: list[str] = []
        self.resolved_image = resolved_image

    def resolve_location(self, location_id: str, image: str) -> tuple[str, str]:
        assert location_id == "lab-1"
        return "provider-1", image or _CATALOG_IMAGE

    def ensure(
        self,
        provider_id: str,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        assert provider_id == "provider-1"
        yield AllocationStatusFrame(
            allocation_id=allocation.allocation_id,
            state=AllocationState.WAITING_FOR_WORKBENCH,
            workbench_id=workbench_id,
            resolved_image=self.resolved_image,
        )

    def release(self, provider_id: str, allocation_id: str) -> None:
        self.released.append(allocation_id)

    def release_best_effort(self, provider_id: str, allocation_id: str) -> bool:
        self.release(provider_id, allocation_id)
        return True

    def is_running(self, provider_id: str, allocation_id: str) -> bool:
        return allocation_id not in self.released


class FakeWorkbench:
    def __init__(self, init_error: Exception | None = None) -> None:
        self.init_error = init_error
        self.assigned: AllocationRequest | None = None
        self.simple_calls: list[list[str]] = []

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        return None

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None:
        self.assigned = allocation

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        self.simple_calls.append(argv)
        if self.init_error is not None:
            raise self.init_error

    def reserve_external(self, allocation_id: str, location_id: str) -> str:
        return location_id

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None:
        return None

    def drain(self, workbench_id: str) -> None:
        return None

    def is_connected(self, workbench_id: str) -> bool:
        return True

    def exec_action(self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        yield ResultFrame(result=ActionResult(status="succeeded"))

    def cancel_run(self, workbench_id: str, run_id: str) -> None:
        return None

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30) -> bytes:
        return b"{}"

    def exec_query_stream(self, workbench_id: str, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        yield b"{}"

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str) -> None:
        return None


def _manager(
    tmp_path: Path, workbench: FakeWorkbench | None = None, provider: FakeProvider | None = None
) -> tuple[WorkbenchManager, AllocationStore, FakeProvider]:
    store = AllocationStore(tmp_path / "allocations.json")
    provider = provider or FakeProvider()
    manager = WorkbenchManager(
        registry=store,
        provider=provider,
        workbench=workbench or FakeWorkbench(),
    )
    return manager, store, provider


def test_provision_records_the_place_and_image_then_assigns(tmp_path: Path) -> None:
    workbench = FakeWorkbench()
    manager, store, _provider = _manager(tmp_path, workbench)

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.location_id == "lab-1"
    assert handle.image == _CATALOG_IMAGE
    assert workbench.assigned is not None
    assert workbench.simple_calls == [["init-ree", "--name", "My REE"]]
    assert store.for_ree("ree-1").state == AllocationState.ASSIGNED  # type: ignore[union-attr]


def test_blank_image_falls_back_to_the_locations_own_catalog(tmp_path: Path) -> None:
    manager, _store, _provider = _manager(tmp_path)

    handle = manager.provision("ree-1", "My REE", location_id="lab-1")

    assert handle.image == _CATALOG_IMAGE


def test_a_bench_that_cannot_take_an_ree_fails_and_is_released(tmp_path: Path) -> None:
    """There is no separate gate: init-ree is what proves the bench usable."""
    workbench = FakeWorkbench(init_error=RuntimeError("/ree is not writable"))
    manager, store, provider = _manager(tmp_path, workbench)

    with pytest.raises(RuntimeError, match="not writable"):
        manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    record = store.for_ree("ree-1")
    assert record is not None
    assert record.state == AllocationState.FAILED
    assert provider.released == [record.request.allocation_id]


def test_the_image_the_bench_came_up_on_wins_over_the_one_asked_for(tmp_path: Path) -> None:
    """A tag moves; the record has to cite what actually ran."""
    pinned = "docker.io/library/docker@sha256:" + "a" * 64
    manager, store, _provider = _manager(tmp_path, provider=FakeProvider(resolved_image=pinned))

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.image == pinned
    record = store.for_ree("ree-1")
    assert record is not None
    # The request keeps what was asked for, so the two remain distinguishable.
    assert record.request.image == _CATALOG_IMAGE
    assert record.resolved_image == pinned


def test_a_provider_that_reports_no_digest_leaves_the_requested_ref_standing(tmp_path: Path) -> None:
    manager, _store, _provider = _manager(tmp_path, provider=FakeProvider(resolved_image=""))

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.image == _CATALOG_IMAGE


def test_teardown_releases_allocation_and_placement(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    manager.teardown(handle)

    assert store.get(handle.allocation_id).state == AllocationState.RELEASED  # type: ignore[union-attr]
    assert store.for_ree("ree-1") is None
    assert provider.released == [handle.allocation_id]
