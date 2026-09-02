from __future__ import annotations

from repo2ree_api.control.compute import list_allocations, list_compute_locations, list_workbench_profiles


def test_compute_catalog_is_empty_without_connected_capacity() -> None:
    assert list_compute_locations().locations == []
    assert list_workbench_profiles().profiles == []


def test_allocation_list_is_a_durable_lifecycle_view() -> None:
    response = list_allocations()
    assert isinstance(response.allocations, list)
