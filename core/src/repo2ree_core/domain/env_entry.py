"""How to *enter* a built runtime artifact.

The entry recipe is a property of the runtime artifact, not of any single
runnable: activation and every experiment enter the runtime the same way.
Each substrate family (container, local, vm, custom) describes how a Working
Environment is provisioned from the artifact.

The matching :class:`WorkingEnvironment` implementation is selected from the
``kind`` discriminator by ``working_environment.manager.acquire``.

Families
--------
container  — Docker, Podman, or Apptainer; parameterised by ``engine``
local      — native workbench, optional venv ``activate`` snippet
vm         — SSH-reachable virtual machine
custom     — author-supplied phased driver scripts

Shared optional fields on every kind
-------------------------------------
activate   — shell snippet sourced before each command (e.g. venv activate)
enter_script — path to a custom driver; overrides the built-in driver when
               present on container/local/vm; *required* for ``custom``
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ================================================
# Per-kind models
# ================================================


class ContainerEntry(BaseModel):
    """Enter the runtime via a container engine (Docker, Podman, or Apptainer).

    The image tarball / .sif file is ``ReeIntent.runtime``; this entry carries
    only the substrate-specific knobs.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["container"] = "container"
    engine: Literal["docker", "podman", "apptainer"] = "docker"
    workdir: str = "/workspace"
    env: dict[str, str] = Field(default_factory=dict)
    gpus: bool = False
    activate: str = ""
    enter_script: str = ""


class LocalEntry(BaseModel):
    """Enter the runtime in the workbench itself — no nested isolation.

    ``activate`` drives venv / conda / module-load use-cases. Without it the
    command runs in the bare workbench shell.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["local"] = "local"
    activate: str = ""
    enter_script: str = ""


class VmEntry(BaseModel):
    """Enter the runtime via SSH into a virtual machine."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["vm"] = "vm"
    cpu: int = 1
    memory: str = "4G"
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_key: str = ""
    activate: str = ""
    enter_script: str = ""


class CustomEntry(BaseModel):
    """Author-supplied phased driver: pre / exec (required) / post scripts."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["custom"] = "custom"
    enter_script: str  # path to a script file or directory of pre/exec/post scripts
    activate: str = ""

    @model_validator(mode="after")
    def _enter_script_required(self) -> CustomEntry:
        if not self.enter_script.strip():
            raise ValueError("enter_script is required for kind='custom'")
        return self


EnvEntry = Annotated[
    ContainerEntry | LocalEntry | VmEntry | CustomEntry,
    Field(discriminator="kind"),
]
