"""Lifecycle identity for obtaining one workbench.

An allocation is bookkeeping around one explicitly selected location/profile.
It is not a scheduling request: there are intentionally no priority, queue,
placement, arbitrary resource, image, or package fields here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.substrate import CompatibilityIssue, ObservedCapabilities, RequiredCapabilities


class LifecycleMode(StrEnum):
    PROVIDER_MANAGED = "provider_managed"
    EXTERNALLY_MANAGED = "externally_managed"


class StoragePolicy(StrEnum):
    EPHEMERAL = "ephemeral"
    RETAINED = "retained"
    EXTERNAL = "external"


class AllocationState(StrEnum):
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    WAITING_FOR_WORKBENCH = "waiting_for_workbench"
    READY = "ready"
    ASSIGNED = "assigned"
    DRAINING = "draining"
    RELEASED = "released"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"
    LOST = "lost"


class ComputeLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    lifecycle_mode: LifecycleMode
    available: bool = True


class WorkbenchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    required: RequiredCapabilities
    storage_policy: StoragePolicy = StoragePolicy.EPHEMERAL


class AllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allocation_id: str = Field(min_length=1)
    ree_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)


class AllocationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AllocationRequest
    state: AllocationState = AllocationState.REQUESTED
    workbench_id: str | None = None
    provider_id: str | None = None
    observation: ObservedCapabilities | None = None
    incompatibilities: tuple[CompatibilityIssue, ...] = ()
    detail: str = ""
    created_at: datetime
    updated_at: datetime
