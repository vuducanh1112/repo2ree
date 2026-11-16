"""The machine ``ree`` runs an REE's scripts on, as ``ree machine`` reports it.

An REE states what its scripts need in its check; whoever provides the compute runs ``ree`` somewhere that passes
it. A workbench reports the machine it runs on for the store it serves.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MachineFacts(BaseModel):
    """The machine ``ree`` runs on: its architecture and GPUs, whether it is a container, and the image the provider
    says it runs in."""

    model_config = ConfigDict(extra="ignore")

    arch: str = ""
    gpus: int = Field(default=0, ge=0)
    container: bool = False
    # The image the compute provider says ree runs in (REPO2REE_IMAGE): reported, not observed.
    reported_image: str | None = None
