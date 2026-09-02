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

from repo2ree_protocol.frames import Frame, WorkbenchRef

# ================================================
# Identity
# ================================================


class ProviderHello(BaseModel):
    """The Docker provider's first message on its capacity-only connection."""

    model_config = ConfigDict(extra="ignore")

    provider_id: str = Field(min_length=1)
    provider_kind: Literal["docker"] = "docker"
    hostname: str = ""
    version: str = ""
    docker_mode: str = ""
    nonce: str = ""


# ================================================
# Specifications
# ================================================


class DockerWorkbenchSpec(BaseModel):
    """Inputs for provisioning a Docker-backed workbench."""

    model_config = ConfigDict(extra="forbid")

    runtime: Literal["docker"] = "docker"
    # Fully resolved by the control plane: a caller-provided base image or the
    # configured default. The provisioning side deliberately applies no image
    # default.
    base_image: str = Field(min_length=1)


# There is one runtime today. Make the request carry a distinct spec now so a
# future discriminated union can grow here without overloading WorkbenchRef or
# adding backend-specific fields to ProvisionRequest.
WorkbenchSpec = DockerWorkbenchSpec


# ================================================
# Requests
# ================================================


class ProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["provision"] = "provision"
    allocation_id: str = Field(min_length=1)
    workbench_id: str = Field(min_length=1)
    enrollment_token: str = Field(min_length=1)
    ree_id: str
    spec: WorkbenchSpec


class RemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["remove"] = "remove"
    ref: WorkbenchRef


class IsRunningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["is_running"] = "is_running"
    ref: WorkbenchRef


class ProviderCancelRequest(BaseModel):
    """Cancel an abandoned in-flight capacity request."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel"] = "cancel"
    request_id: str


# Tagged union discriminated on 'op': every capacity call.
ProviderRequest = Annotated[
    ProvisionRequest | RemoveRequest | IsRunningRequest | ProviderCancelRequest,
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
