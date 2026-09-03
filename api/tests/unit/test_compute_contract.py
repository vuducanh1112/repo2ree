from __future__ import annotations

from repo2ree_api.control.compute import list_allocations, list_compute_locations
from repo2ree_protocol import ComputeLocation


def test_compute_catalog_is_empty_without_connected_capacity() -> None:
    assert list_compute_locations().locations == []


def test_a_location_carries_its_own_image_catalog_and_nothing_about_what_it_supplies() -> None:
    """The catalog is published outward; no field describes the image's contents."""
    forbidden = {"capabilities", "required", "substrate", "software", "profiles"}

    assert not forbidden & set(ComputeLocation.model_fields)
    assert {"images", "accepts_custom_image"} <= set(ComputeLocation.model_fields)


def test_allocation_list_is_a_durable_lifecycle_view() -> None:
    response = list_allocations()
    assert isinstance(response.allocations, list)
