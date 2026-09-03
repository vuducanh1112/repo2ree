from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_protocol import AllocationRequest, AllocationState
from repo2ree_supervisor import AllocationStore


def _request(allocation_id: str = "alloc-1", ree_id: str = "ree-1") -> AllocationRequest:
    return AllocationRequest(
        allocation_id=allocation_id,
        ree_id=ree_id,
        location_id="lab-1",
        image="docker.io/library/docker:29-dind",
    )


def test_allocation_and_placement_survive_store_restart(tmp_path: Path) -> None:
    path = tmp_path / "allocations.json"
    store = AllocationStore(path)
    store.create(_request(), provider_id="provider-1", workbench_id="wb-1")
    store.update("alloc-1", AllocationState.PROVISIONING)

    restored = AllocationStore(path).for_ree("ree-1")

    assert restored is not None
    assert restored.state == AllocationState.PROVISIONING
    assert restored.workbench_id == "wb-1"


def test_allocation_rejects_illegal_transition(tmp_path: Path) -> None:
    store = AllocationStore(tmp_path / "allocations.json")
    store.create(_request(), provider_id="provider-1", workbench_id="wb-1")

    with pytest.raises(ValueError, match="requested -> assigned"):
        store.update("alloc-1", AllocationState.ASSIGNED)


def test_one_ree_has_one_active_placement(tmp_path: Path) -> None:
    store = AllocationStore(tmp_path / "allocations.json")
    store.create(_request(), provider_id="provider-1", workbench_id="wb-1")

    with pytest.raises(ValueError, match="already has an allocation"):
        store.create(_request("alloc-2"), provider_id="provider-1", workbench_id="wb-2")

    store.remove_placement("ree-1")
    store.create(_request("alloc-2"), provider_id="provider-1", workbench_id="wb-2")


def test_a_record_from_an_older_build_is_dropped_rather_than_failing_every_read(tmp_path: Path) -> None:
    """The file outlives the schema; one unreadable record must not take the rest with it."""
    store = AllocationStore(tmp_path / "allocations.json")
    store.create(_request(), provider_id="provider-1", workbench_id="wb-1")
    path = tmp_path / "allocations.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["allocations"]["alloc-legacy"] = {
        "request": {
            "allocation_id": "alloc-legacy",
            "ree_id": "ree-legacy",
            "location_id": "lab-1",
            "profile_id": "standard",
            "profile_revision": "1",
        },
        "state": "released",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    assert [record.request.allocation_id for record in store.list()] == ["alloc-1"]
    assert store.get("alloc-legacy") is None
