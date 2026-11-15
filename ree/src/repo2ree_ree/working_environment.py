"""What an REE's scripts run in: declared by the author, and observed by each step that ran in it.

The working environment is an OCI image the scripts run in, or, undeclared, the machine that runs the step. The
REE does not build it: an image is named, and pinned by its digest, as a workflow engine names the container of a
task. Every script, the build included, runs in it; a launch, where the REE declares one, runs outside it, so a
scheduler places a job and the job enters the image on the node it landed on.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_ree.layout import digest_of
from repo2ree_ree.primitives import Digest

# Where a step's script runs: a container from the environment's image, or the host itself.
EnvironmentBackend = Literal["host", "container"]
# The container engine the script could reach: none, the host's own (its socket mounted), or a
# daemon nested inside the environment (the privileged benches before stores).
ScriptEngine = Literal["none", "socket", "nested"]
# Where a step found the image it ran: the engine had it or pulled it, or the REE's bundle carried it.
ImageSource = Literal["engine", "bundle"]


class _WorkingEnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkingEnvironment(_WorkingEnvironmentModel):
    # An OCI image reference, pinned or not ("ref@sha256:<hex>" is pinned).
    oci: str = Field(min_length=1)

    @property
    def pinned(self) -> bool:
        return "@sha256:" in self.oci

    @property
    def digest(self) -> str | None:
        """The digest that pins the image; None when the reference is not pinned."""
        return self.oci.rpartition("@")[2] if self.pinned else None


def backend_of(declared: WorkingEnvironment | None) -> EnvironmentBackend:
    return "host" if declared is None else "container"


class HostFingerprint(_WorkingEnvironmentModel):
    os: str = Field(min_length=1)
    arch: str = Field(min_length=1)
    kernel: str = ""
    container_engine: str = ""


class WorkingEnvironmentObservation(_WorkingEnvironmentModel):
    """What a step ran in: the declaration it ran under, and what was there."""

    declared: WorkingEnvironment | None = None
    backend: EnvironmentBackend
    image_digest: Annotated[Digest | None, digest_of("outside")] = None
    image_source: ImageSource | None = None
    host: HostFingerprint | None = None
    script_engine: ScriptEngine = "none"

    @model_validator(mode="after")
    def _observed_where_it_ran(self) -> WorkingEnvironmentObservation:
        if self.backend == "container" and self.image_digest is None:
            raise ValueError("a step run in a container records the image digest it ran")
        if self.backend == "host" and self.host is None:
            raise ValueError("a step run on the host records the host it ran on")
        return self
