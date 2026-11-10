"""What an REE's scripts run in: declared by the author, and observed by each step that ran in it.

The build script is the author's own and may need anything, a container engine included; the
environment is what provides it. Activation and experiments run in the same environment, on the
experiment environment the build produced. An ``image`` environment is a container image; a ``host`` environment
is whatever machine runs the step, described only by what was observed there.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_ree.primitives import Digest

WorkbenchEnvironmentKind = Literal["image", "host"]
# Where a step's script ran: a container from the environment's image, or the host itself.
EnvironmentBackend = Literal["host", "container"]
# The container engine the script could reach: none, the host's own (its socket mounted), or a
# daemon nested inside the environment (the privileged benches before stores).
ScriptEngine = Literal["none", "socket", "nested"]


class _WorkbenchEnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkbenchEnvironment(_WorkbenchEnvironmentModel):
    kind: WorkbenchEnvironmentKind
    # A reference, pinned or not ("ref@sha256:<hex>" is pinned); only for an image environment.
    image: str | None = Field(default=None, min_length=1)
    needs_container_engine: bool = False

    @model_validator(mode="after")
    def _image_only_for_images(self) -> WorkbenchEnvironment:
        if self.kind == "image" and self.image is None:
            raise ValueError("an image environment names its image")
        if self.kind == "host" and self.image is not None:
            raise ValueError("a host environment names no image")
        return self

    @property
    def pinned(self) -> bool:
        return self.image is not None and "@sha256:" in self.image


class HostFingerprint(_WorkbenchEnvironmentModel):
    os: str = Field(min_length=1)
    arch: str = Field(min_length=1)
    kernel: str = ""
    container_engine: str = ""


class WorkbenchEnvironmentObservation(_WorkbenchEnvironmentModel):
    """What a step ran in: the declaration it ran under, and what was there."""

    declared: WorkbenchEnvironment | None = None
    backend: EnvironmentBackend
    image_digest: Digest | None = None
    host: HostFingerprint | None = None
    script_engine: ScriptEngine = "none"

    @model_validator(mode="after")
    def _observed_where_it_ran(self) -> WorkbenchEnvironmentObservation:
        if self.backend == "container" and self.image_digest is None:
            raise ValueError("a step run in a container records the image digest it ran")
        if self.backend == "host" and self.host is None:
            raise ValueError("a step run on the host records the host it ran on")
        return self
