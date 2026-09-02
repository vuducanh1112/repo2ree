"""Read-only compute catalog and allocation lifecycle views."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import allocation_store, provider_connections, workbench_connections
from repo2ree_protocol import (
    AllocationRecord,
    ComputeLocation,
    LifecycleMode,
    RequiredCapabilities,
    StoragePolicy,
    WorkbenchProfile,
)

compute_router = APIRouter(tags=["compute"])


class ComputeLocationList(BaseModel):
    locations: list[ComputeLocation]


class WorkbenchProfileList(BaseModel):
    profiles: list[WorkbenchProfile]


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
        )
        for provider in provider_connections.list_providers()
    ]
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
    "/api/v1/workbench-profiles",
    response_model=WorkbenchProfileList,
    responses=ERROR_RESPONSES,
    operation_id="listWorkbenchProfiles",
)
def list_workbench_profiles(location_id: str | None = Query(None)) -> WorkbenchProfileList:
    profiles = [profile for provider in provider_connections.list_providers() for profile in provider.profiles]
    profiles.extend(
        WorkbenchProfile(
            id=bench.profile_id,
            revision=bench.profile_revision,
            location_id=bench.location_id,
            label=bench.profile_id,
            required=RequiredCapabilities(
                substrate=bench.capabilities.substrate,
                resources=bench.capabilities.resources,
            ),
            storage_policy=StoragePolicy.EXTERNAL,
        )
        for bench in workbench_connections.list_workbenches()
        if bench.mode == "external" and bench.capabilities is not None
    )
    if location_id is not None:
        profiles = [profile for profile in profiles if profile.location_id == location_id]
    return WorkbenchProfileList(profiles=profiles)


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
