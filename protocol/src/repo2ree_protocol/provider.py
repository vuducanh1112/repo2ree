"""The capacity wire vocabulary: creating and releasing execution environments.

These are the requests the control plane sends to the *provisioning* side — the
adapter that turns a workbench specification into a real environment and tears
it down again. Nothing here can execute an REE command; that is
``repo2ree_protocol.workbench``'s vocabulary, and the two are kept disjoint so
capacity credentials and execution credentials can never authorize each other's
operations.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.allocation import AllocationRequest, WorkbenchProfile
from repo2ree_protocol.frames import Frame

# ================================================
# Identity
# ================================================


class ProviderHello(BaseModel):
    """The Docker provider's first message on its capacity-only connection."""

    model_config = ConfigDict(extra="ignore")

    provider_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    location_label: str = Field(min_length=1)
    provider_kind: Literal["docker"] = "docker"
    hostname: str = ""
    version: str = ""
    profiles: tuple[WorkbenchProfile, ...] = ()
    nonce: str = ""


# ================================================
# Requests
# ================================================


class EnsureAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["ensure_allocation"] = "ensure_allocation"
    allocation: AllocationRequest
    workbench_id: str = Field(min_length=1)
    enrollment_token: str = Field(min_length=1)


class ReleaseAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["release_allocation"] = "release_allocation"
    allocation_id: str = Field(min_length=1)


class InspectAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["inspect_allocation"] = "inspect_allocation"
    allocation_id: str = Field(min_length=1)


class ProviderCancelRequest(BaseModel):
    """Cancel an abandoned in-flight capacity request."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel"] = "cancel"
    request_id: str


# Tagged union discriminated on 'op': every capacity call.
ProviderRequest = Annotated[
    EnsureAllocationRequest | ReleaseAllocationRequest | InspectAllocationRequest | ProviderCancelRequest,
    Field(discriminator="op"),
]


class ProviderWsRequest(BaseModel):
    """A control-plane call on the capacity-only provider connection."""

    model_config = ConfigDict(extra="forbid")

    id: str
    request: ProviderRequest
    traceparent: str | None = None


class ProviderWsMessage(BaseModel):
    """A provider response frame correlated to a capacity request."""

    model_config = ConfigDict(extra="forbid")

    id: str
    frame: Frame


provider_hello_adapter: TypeAdapter[ProviderHello] = TypeAdapter(ProviderHello)
provider_ws_request_adapter: TypeAdapter[ProviderWsRequest] = TypeAdapter(ProviderWsRequest)
provider_ws_message_adapter: TypeAdapter[ProviderWsMessage] = TypeAdapter(ProviderWsMessage)
