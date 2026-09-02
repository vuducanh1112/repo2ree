from __future__ import annotations

import pytest
from pydantic import ValidationError

from repo2ree_protocol import AllocationRequest, FixedResources, RequiredCapabilities, SubstrateKind


def test_allocation_request_contains_identity_not_scheduler_or_package_inputs() -> None:
    request = AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        profile_id="standard",
        profile_revision="1",
    )

    assert set(request.model_dump()) == {
        "allocation_id",
        "ree_id",
        "location_id",
        "profile_id",
        "profile_revision",
    }
    with pytest.raises(ValidationError):
        AllocationRequest.model_validate({**request.model_dump(), "image": "arbitrary:latest"})


def test_fixed_profile_resources_are_descriptive_and_positive() -> None:
    required = RequiredCapabilities(
        substrate=SubstrateKind.DOCKER_NESTED,
        resources=FixedResources(cpu_count=4, memory_bytes=16 * 1024**3),
    )

    assert required.resources.cpu_count == 4
    with pytest.raises(ValidationError):
        FixedResources(cpu_count=0)
