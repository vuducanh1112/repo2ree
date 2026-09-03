from __future__ import annotations

import pytest
from pydantic import ValidationError

from repo2ree_protocol import AllocationRequest, ComputeLocation, LifecycleMode, WorkbenchImage


def test_allocation_request_names_a_place_and_an_image_and_nothing_else() -> None:
    request = AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        image="docker.io/library/docker:29-dind",
    )

    assert set(request.model_dump()) == {"allocation_id", "ree_id", "location_id", "image"}
    with pytest.raises(ValidationError):
        AllocationRequest.model_validate({**request.model_dump(), "cpu_count": 4})


def test_no_allocation_model_describes_what_an_image_supplies() -> None:
    """The control plane selects an image; it never reasons about one.

    A field naming a capability, a package, or a version constraint is how this
    turns into an environment manager, so the absence is asserted rather than
    left to review.
    """
    location = ComputeLocation(id="lab-1", label="Lab 1", lifecycle_mode=LifecycleMode.PROVIDER_MANAGED)
    forbidden = {"capabilities", "required", "substrate", "software", "resources", "packages"}

    for model in (AllocationRequest, ComputeLocation, WorkbenchImage):
        assert not forbidden & set(model.model_fields)
    assert set(location.images) == set()


def test_catalog_entry_needs_only_a_ref() -> None:
    image = WorkbenchImage(ref="docker:29-dind")

    assert image.id == "docker:29-dind"
    assert image.label == "docker:29-dind"
    with pytest.raises(ValidationError):
        WorkbenchImage(ref="")
