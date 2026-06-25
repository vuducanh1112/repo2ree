"""How to *enter* a built runtime artifact.

The entry recipe is a property of the runtime artifact, not of any single
runnable: activation and every experiment enter the runtime the same way.

The model is **presets over a single phased lifecycle**. ``kind`` (+ ``engine``
for containers) selects a *preset* that supplies default ``provision`` / ``exec``
/ ``teardown`` phase commands; :class:`PhaseOverrides` lets any phase be replaced
by an author script. ``custom`` is the limit case where every phase is overridden
and there is no preset default. See ``docs/engineering/substrate-drivers.md``.

The matching :class:`WorkingEnvironment` implementation is selected from the
``kind`` discriminator by ``working_environment.manager.acquire``.

Families
--------
container  — Docker, Podman, or Apptainer; parameterised by ``engine``
local      — native workbench, optional venv ``activate`` snippet
vm         — SSH-reachable virtual machine
custom     — author-supplied phased driver scripts (sugar over ``overrides``)

Shared fields on every kind (via :class:`_SubstrateBase`)
---------------------------------------------------------
activate   — shell snippet sourced before each command (e.g. venv activate)
overrides  — per-phase scripts that replace the preset's generated defaults
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ================================================
# Phase overrides
# ================================================


class PhaseOverrides(BaseModel):
    """Author scripts that replace a substrate preset's default lifecycle phase.

    Each value is a workspace-relative path to a script (single file). An empty
    string means "use the preset default for that phase". This is the whole
    preset/override reframe in one type: keep Docker's ``provision``/``teardown``
    and override only ``exec``, etc. ``custom`` is the case where all three are
    set and no preset default applies.
    """

    model_config = ConfigDict(extra="forbid")

    provision: str = ""  # instantiate the runtime, place the workspace
    exec: str = ""  # run "$R2R_COMMAND" inside the runtime
    teardown: str = ""  # collect outputs, tear the runtime down (always runs)

    def any_set(self) -> bool:
        return bool(self.provision.strip() or self.exec.strip() or self.teardown.strip())


# ================================================
# Shared base
# ================================================


class _SubstrateBase(BaseModel):
    """Cross-cutting knobs every substrate preset shares.

    ``activate`` is sourced before each command; ``overrides`` replaces preset
    default phases with author scripts. Both default to "use the preset as-is".
    """

    model_config = ConfigDict(extra="forbid")

    activate: str = ""
    overrides: PhaseOverrides = Field(default_factory=PhaseOverrides)


# ================================================
# Per-kind presets
# ================================================


class ContainerEntry(_SubstrateBase):
    """Enter the runtime via a container engine (Docker, Podman, or Apptainer).

    The image tarball / .sif file is ``ReeIntent.runtime``; this entry carries
    only the substrate-specific knobs. The REE workspace is copied to
    ``/workspace`` by the container preset; runnable commands should use
    explicit paths (for example ``cd code && bash run``) when they need a
    subdirectory.
    """

    kind: Literal["container"] = "container"
    engine: Literal["docker", "podman", "apptainer"] = "docker"
    env: dict[str, str] = Field(default_factory=dict)
    # Raw flags spliced into `<engine> create` before the image name, e.g.
    # ["--volume", "/data:/data", "--mac-address", "12:34:56:78:9a:bc"].
    # Passthrough: repo2ree does not validate them — they are disclosed in the
    # command plan and sealed into the manifest as declared runtime provenance.
    create_args: list[str] = Field(default_factory=list)


class LocalEntry(_SubstrateBase):
    """Enter the runtime in the workbench itself — no nested isolation.

    ``activate`` drives venv / conda / module-load use-cases. Without it the
    command runs in the bare workbench shell.
    """

    kind: Literal["local"] = "local"


class VmEntry(_SubstrateBase):
    """Enter the runtime via SSH into a virtual machine."""

    kind: Literal["vm"] = "vm"
    cpu: int = 1
    memory: str = "4G"
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_key: str = ""


class CustomEntry(_SubstrateBase):
    """Author-supplied phased driver — the limit case with no preset default.

    ``enter_script`` points at a single file (the ``exec`` phase) or a directory
    of ``pre``/``exec``/``post`` scripts; it is the custom substrate's way of
    expressing the same phased lifecycle the ``overrides`` field expresses for
    built-in presets. ``enter_script`` is required. (Slice 2 unifies the two by
    expanding ``enter_script`` into ``overrides``; until then the scripted
    environment consumes ``enter_script`` directly.)
    """

    kind: Literal["custom"] = "custom"
    enter_script: str  # path to a script file or directory of pre/exec/post scripts

    @model_validator(mode="after")
    def _enter_script_required(self) -> CustomEntry:
        if not self.enter_script.strip():
            raise ValueError("enter_script is required for kind='custom'")
        return self


EnvEntry = Annotated[
    ContainerEntry | LocalEntry | VmEntry | CustomEntry,
    Field(discriminator="kind"),
]
