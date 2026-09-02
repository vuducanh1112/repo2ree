from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol import (
    ActionResult,
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    FixedResources,
    Frame,
    ObservedCapabilities,
    RequiredCapabilities,
    ResultFrame,
    SubstrateKind,
    WorkbenchProfile,
)
from repo2ree_supervisor import AllocationStore, WorkbenchManager


def _profile(substrate: SubstrateKind = SubstrateKind.DOCKER_NESTED) -> WorkbenchProfile:
    return WorkbenchProfile(
        id="standard",
        revision="1",
        location_id="lab-1",
        label="Standard",
        required=RequiredCapabilities(substrate=substrate, resources=FixedResources()),
    )


class FakeProvider:
    def __init__(self) -> None:
        self.released: list[str] = []

    def resolve_profile(self, location_id: str, profile_id: str) -> tuple[str, WorkbenchProfile]:
        assert (location_id, profile_id) == ("lab-1", "standard")
        return "provider-1", _profile()

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
        )

    def release(self, provider_id: str, allocation_id: str) -> None:
        self.released.append(allocation_id)

    def release_best_effort(self, provider_id: str, allocation_id: str) -> bool:
        self.release(provider_id, allocation_id)
        return True

    def is_running(self, provider_id: str, allocation_id: str) -> bool:
        return allocation_id not in self.released


class FakeWorkbench:
    def __init__(self, observation: ObservedCapabilities | None = None) -> None:
        self.observed = observation or ObservedCapabilities(
            root_writable=True,
            executor_available=True,
            substrate=SubstrateKind.DOCKER_NESTED,
            docker_version="29.0.0",
        )
        self.assigned: AllocationRequest | None = None
        self.simple_calls: list[list[str]] = []

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        return None

    def observation(self, workbench_id: str) -> ObservedCapabilities:
        return self.observed

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None:
        self.assigned = allocation

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        self.simple_calls.append(argv)

    def reserve_external(self, allocation_id: str, location_id: str, profile_id: str) -> tuple[str, WorkbenchProfile]:
        return location_id, _profile(self.observed.substrate).model_copy(
            update={"location_id": location_id, "id": profile_id}
        )

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
    tmp_path: Path, workbench: FakeWorkbench | None = None
) -> tuple[WorkbenchManager, AllocationStore, FakeProvider]:
    store = AllocationStore(tmp_path / "allocations.json")
    provider = FakeProvider()
    manager = WorkbenchManager(
        registry=store,
        provider=provider,
        workbench=workbench or FakeWorkbench(),
    )
    return manager, store, provider


def test_provision_validates_then_assigns_a_durable_allocation(tmp_path: Path) -> None:
    workbench = FakeWorkbench()
    manager, store, _provider = _manager(tmp_path, workbench)

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", profile_id="standard")

    assert handle.location_id == "lab-1"
    assert handle.profile_id == "standard"
    assert workbench.assigned is not None
    assert workbench.simple_calls == [["init-ree", "--name", "My REE"]]
    assert store.for_ree("ree-1").state == AllocationState.ASSIGNED  # type: ignore[union-attr]


def test_incompatible_workbench_is_not_assigned_and_is_released(tmp_path: Path) -> None:
    workbench = FakeWorkbench(
        ObservedCapabilities(root_writable=True, executor_available=True, substrate=SubstrateKind.BARE)
    )
    manager, store, provider = _manager(tmp_path, workbench)

    with pytest.raises(RuntimeError, match="incompatible"):
        manager.provision("ree-1", "My REE", location_id="lab-1", profile_id="standard")

    record = store.for_ree("ree-1")
    assert record is not None
    assert record.state == AllocationState.INCOMPATIBLE
    assert record.incompatibilities[0].code == "substrate_mismatch"
    assert workbench.assigned is None
    assert provider.released == [record.request.allocation_id]


def test_teardown_releases_allocation_and_placement(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", profile_id="standard")

    manager.teardown(handle)

    assert store.get(handle.allocation_id).state == AllocationState.RELEASED  # type: ignore[union-attr]
    assert store.for_ree("ree-1") is None
    assert provider.released == [handle.allocation_id]
