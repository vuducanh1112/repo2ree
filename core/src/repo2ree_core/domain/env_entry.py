"""How to *enter* a built runtime artifact.

The entry recipe is a property of the runtime artifact, not of any single
runnable: activation and every experiment enter the runtime the same way.
Each substrate (Docker container, Singularity image, VM, or the workbench
itself) describes how a Working Environment is provisioned from the artifact.

The matching :class:`WorkingEnvironment` implementation is selected from the
``kind`` discriminator by ``working_environment.manager.acquire``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DockerEntry(BaseModel):
    """Enter the runtime by loading its image tarball and exec-ing in a container.

    The image tarball itself is the REE's ``runtime`` artifact path; this entry
    carries only the substrate-specific knowledge of *how* to inhabit it.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker"] = "docker"


class SingularityEntry(BaseModel):
    """Enter the runtime via ``singularity exec`` against a ``.sif`` image."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["singularity"] = "singularity"
    sif: str = ""  # path to the .sif image, relative to the workspace


class VmEntry(BaseModel):
    """Enter the runtime by connecting to a virtual machine and running there."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["vm"] = "vm"
    host: str = ""  # ssh target or serial endpoint


class NativeEntry(BaseModel):
    """Enter the runtime in the workbench itself — no nested isolation.

    Used when the runtime *is* the workbench plus, optionally, an environment
    that has to be sourced first (e.g. a virtualenv). ``activate`` is prefixed
    before every command run in this substrate.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["native"] = "native"
    activate: str = ""  # e.g. "source .venv/bin/activate"


EnvEntry = Annotated[
    DockerEntry | SingularityEntry | VmEntry | NativeEntry,
    Field(discriminator="kind"),
]
