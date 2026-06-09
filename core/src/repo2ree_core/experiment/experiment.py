from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Experiment names are used as a path segment when running an experiment
# (".../experiments/{name}:run"), so they must stay free of characters that
# break URL routing — chiefly "/" (and the "." / ".." path segments).
EXPERIMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ._-]+$")


class FileSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["file"]
    path: str


class StdoutSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stdout"]


class StderrSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stderr"]


OutputSource = Annotated[
    FileSource | StdoutSource | StderrSource,
    Field(discriminator="kind"),
]


class Sha256Match(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["sha256"]
    value: str


class ContainsMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["contains"]
    value: str


class RegexMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["regex"]
    value: str


class NumericMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["numeric"]
    value: str  # expected number as a string to avoid JSON float precision loss
    epsilon: float


class CustomMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["custom"]
    value: str  # shell command; receives actual output via stdin, exits 0 for match


OutputMatch = Annotated[
    Sha256Match | ContainsMatch | RegexMatch | NumericMatch | CustomMatch,
    Field(discriminator="mode"),
]


class ExpectedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: OutputSource
    match: OutputMatch


class ResourceEstimates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: str = ""
    memory: str = ""
    gpu: str = ""
    storage: str = ""
    network: str = ""


class Experiment(BaseModel):
    """Experiment metadata attached to a REE draft."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str = ""
    command: str = ""
    outputs: list[ExpectedOutput] = Field(default_factory=list)
    runtime_estimate: str = ""
    resource_estimates: ResourceEstimates = Field(default_factory=ResourceEstimates)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if value == "":  # in-progress drafts may not have named the experiment yet
            return value
        if value in {".", ".."} or not EXPERIMENT_NAME_PATTERN.match(value):
            raise ValueError("experiment name may only contain letters, digits, spaces, '.', '_' and '-'")
        return value
