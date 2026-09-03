"""Read-only compute catalog and allocation lifecycle views."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import allocation_store, provider_connections, workbench_connections
from repo2ree_protocol import AllocationRecord, ComputeLocation, LifecycleMode

compute_router = APIRouter(tags=["compute"])


class ComputeLocationList(BaseModel):
    locations: list[ComputeLocation]


class AllocationList(BaseModel):
    allocations: list[AllocationRecord]


@compute_router.get(
    "/api/v1/compute-locations",
    response_model=ComputeLocationList,
    responses=ERROR_RESPONSES,
    operation_id="listComputeLocations",
)
def list_compute_locations() -> ComputeLocationList:
    locations = [
        ComputeLocation(
            id=provider.location_id,
            label=provider.location_label,
            lifecycle_mode=LifecycleMode.PROVIDER_MANAGED,
            available=True,
            images=provider.images,
            accepts_custom_image=provider.accepts_custom_image,
        )
        for provider in provider_connections.list_providers()
    ]
    # An externally managed bench was provisioned outside this control plane, so
    # it publishes no catalog and takes no image: there is nothing left to pick.
    locations.extend(
        ComputeLocation(
            id=bench.location_id,
            label=bench.hostname or bench.location_id,
            lifecycle_mode=LifecycleMode.EXTERNALLY_MANAGED,
            available=bench.available,
        )
        for bench in workbench_connections.list_workbenches()
        if bench.mode == "external"
    )
    return ComputeLocationList(locations=sorted(locations, key=lambda location: (location.label, location.id)))


@compute_router.get(
    "/api/v1/allocations",
    response_model=AllocationList,
    responses=ERROR_RESPONSES,
    operation_id="listAllocations",
)
def list_allocations() -> AllocationList:
    return AllocationList(allocations=allocation_store.list())


@compute_router.get(
    "/api/v1/allocations/{allocation_id}",
    response_model=AllocationRecord,
    responses=ERROR_RESPONSES,
    operation_id="getAllocation",
)
def get_allocation(allocation_id: str) -> AllocationRecord:
    record = allocation_store.get(allocation_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"allocation {allocation_id!r} was not found")
    return record
