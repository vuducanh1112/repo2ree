"""Capacity and execution sockets reject each other's authority."""

import pytest
from pydantic import ValidationError

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.provider import (
    EnsureAllocationRequest,
    ProviderWsRequest,
    provider_ws_request_adapter,
)
from repo2ree_protocol.workbench import (
    ExecSimpleRequest,
    WorkbenchWsRequest,
    workbench_ws_request_adapter,
)


def test_provider_socket_rejects_execution_request() -> None:
    execution = WorkbenchWsRequest(
        id="request-1",
        request=ExecSimpleRequest(argv=["get-ree-manifest"]),
    )

    with pytest.raises(ValidationError):
        provider_ws_request_adapter.validate_json(execution.model_dump_json())


def test_workbench_socket_rejects_capacity_request() -> None:
    opaque_enrollment = "test-enrollment-value"
    capacity = ProviderWsRequest(
        id="request-1",
        request=EnsureAllocationRequest(
            allocation=AllocationRequest(
                allocation_id="allocation-1",
                ree_id="ree-1",
                location_id="lab-1",
                image="docker:29-dind",
            ),
            workbench_id="workbench-1",
            enrollment_token=opaque_enrollment,
        ),
    )

    with pytest.raises(ValidationError):
        workbench_ws_request_adapter.validate_json(capacity.model_dump_json())
