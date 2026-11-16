"""How a machine runs an REE's scripts, as ``ree machine`` reports it.

The REE declares what its scripts run in (``definition.working_environment``): an image, or the machine itself. The
machine only enters it: with the first engine it has, and, for now, letting a script in a container reach that
engine where it is told to. A workbench reports this for the store it serves.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# How this machine enters an OCI image: an engine, or none at all.
EngineName = Literal["docker", "podman", "apptainer", "none"]
# Whether a script in a container may reach the machine's engine through its socket.
ScriptEngineAccess = Literal["none", "socket"]


class MachineFacts(BaseModel):
    """How this machine runs an REE's scripts, and what it offers them."""

    model_config = ConfigDict(extra="ignore")

    arch: str = ""
    engine: EngineName = "none"
    script_engine: ScriptEngineAccess = "none"
    gpus: int = Field(default=0, ge=0)
