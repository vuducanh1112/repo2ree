from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Experiment(BaseModel):
    """Experiment metadata attached to a REE draft."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str = ""
    command: str = ""
