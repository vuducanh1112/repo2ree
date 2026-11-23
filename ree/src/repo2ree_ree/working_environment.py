from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _WorkingEnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HostFingerprint(_WorkingEnvironmentModel):
    os: str = Field(min_length=1)
    arch: str = Field(min_length=1)
    kernel: str = ""


class WorkingEnvironmentObservation(_WorkingEnvironmentModel):
    host: HostFingerprint
    container: bool = False
