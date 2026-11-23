from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MachineFacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    arch: str = ""
    gpus: int = Field(default=0, ge=0)
    container: bool = False
