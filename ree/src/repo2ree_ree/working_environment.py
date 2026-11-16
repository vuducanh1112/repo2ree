"""What a step's scripts ran in: the working environment, as the step observed it.

The REE does not declare its working environment; it states what its scripts need in its check
(``ree-scripts/check_working_environment.sh``), and whoever provides the compute runs ``ree`` somewhere that passes
it: a host with its toolchain, a container from an image of their choosing, a cluster's nodes. Each step records
where that was: the host, whether ``ree`` ran in a container, and the image when the provider says which.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _WorkingEnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HostFingerprint(_WorkingEnvironmentModel):
    os: str = Field(min_length=1)
    arch: str = Field(min_length=1)
    kernel: str = ""


class WorkingEnvironmentObservation(_WorkingEnvironmentModel):
    """Where a step's scripts ran: the host as the step saw it, and the image the provider reported running it in."""

    host: HostFingerprint
    # Whether ree ran in a container: the host is then the container's view of it.
    container: bool = False
    # The image the compute provider says ree ran in (REPO2REE_IMAGE), as it said it: reported, not observed.
    reported_image: str | None = Field(default=None, min_length=1)
