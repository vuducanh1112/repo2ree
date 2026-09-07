"""Lifecycle identity for obtaining one workbench.

An allocation is bookkeeping around one explicitly selected location and base
image. It is not a scheduling request: there are intentionally no priority,
queue, placement, or resource fields here, and nothing describes what the image
*supplies* — the control plane selects an image, it does not reason about one.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_protocol.build import BuildInfo


class LifecycleMode(StrEnum):
    PROVIDER_MANAGED = "provider_managed"
    EXTERNALLY_MANAGED = "externally_managed"


class AllocationState(StrEnum):
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    WAITING_FOR_WORKBENCH = "waiting_for_workbench"
    READY = "ready"
    ASSIGNED = "assigned"
    DRAINING = "draining"
    RELEASED = "released"
    FAILED = "failed"
    LOST = "lost"


class WorkbenchImage(BaseModel):
    """One base image a location offers to provision workbenches from.

    Only ``ref`` is meaningful to the backend — it is the image that gets run.
    ``id``/``label``/``description`` are picker-facing and default off the ref,
    so a catalog entry can be as terse as ``{"ref": "docker:29-dind"}``.
    """

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1)
    id: str = ""
    label: str = ""
    description: str = ""

    @model_validator(mode="after")
    def _default_picker_fields_from_ref(self) -> WorkbenchImage:
        # A ref uniquely identifies an entry, so it doubles as a stable id; the
        # label falls back to it too. Description is optional — blank reads fine.
        self.id = self.id or self.ref
        self.label = self.label or self.ref
        return self


class ConnectedComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["provider", "workbench"]
    build: BuildInfo = Field(default_factory=BuildInfo)


class ComputeLocation(BaseModel):
    """A place workbenches can be obtained, and the images it offers there.

    The catalog is published *outward*: the author picks from it, and the
    resolved ref is recorded on the allocation. A location that accepts a ref it
    did not publish says so with ``accepts_custom_image``; nothing else about
    the image is negotiated.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    lifecycle_mode: LifecycleMode
    available: bool = True
    # Empty for an externally managed location: its bench already exists, so
    # there is no image left to choose.
    images: tuple[WorkbenchImage, ...] = ()
    accepts_custom_image: bool = False
    connected_component: ConnectedComponent | None = None


class AllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allocation_id: str = Field(min_length=1)
    ree_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    # The image ref this bench is built from, resolved against the location's
    # catalog before the request is made. Blank only for an externally managed
    # location, whose bench was provisioned outside this control plane.
    image: str = ""


class AllocationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AllocationRequest
    state: AllocationState = AllocationState.REQUESTED
    workbench_id: str | None = None
    provider_id: str | None = None
    # What the provider actually ran, pinned by digest where the runtime could
    # resolve one. The request says which image was asked for; this says which
    # one arrived, and the two differ whenever a tag has moved.
    resolved_image: str = ""
    detail: str = ""
    created_at: datetime
    updated_at: datetime
