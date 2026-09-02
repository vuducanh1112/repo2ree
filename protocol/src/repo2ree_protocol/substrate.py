"""Provider-neutral requirements and observations for one workbench.

The models deliberately describe capabilities only.  They cannot carry an
image, package list, launch command, or placement preference: those are owned
by the selected location's provider.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SubstrateKind(StrEnum):
    BARE = "bare"
    DOCKER_NESTED = "docker-nested"
    DOCKER_HOST_SOCKET = "docker-host-socket"


class FixedResources(BaseModel):
    """Informational limits attached to a fixed deployment profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cpu_count: float | None = Field(default=None, gt=0)
    memory_bytes: int | None = Field(default=None, gt=0)


class RequiredCapabilities(BaseModel):
    """The exact capability gate for a profile, never a placement query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    substrate: SubstrateKind
    minimum_docker_version: str | None = None
    resources: FixedResources = Field(default_factory=FixedResources)


class ObservedCapabilities(BaseModel):
    """Facts measured by the workbench from inside its environment."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    root_writable: bool = False
    executor_available: bool = False
    substrate: SubstrateKind = SubstrateKind.BARE
    docker_version: str | None = None
    docker_socket_mounted: bool = False
    resources: FixedResources = Field(default_factory=FixedResources)


class CompatibilityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    expected: str | None = None
    observed: str | None = None
