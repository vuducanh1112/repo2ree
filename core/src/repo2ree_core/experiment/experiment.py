from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _FileSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["file"]
    path: str


class _StdoutSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stdout"]


class _StderrSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stderr"]


OutputSource = Annotated[
    _FileSource | _StdoutSource | _StderrSource,
    Field(discriminator="kind"),
]


class _Sha256Match(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["sha256"]
    value: str


class _ContainsMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["contains"]
    value: str


class _RegexMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["regex"]
    value: str


class _NumericMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["numeric"]
    value: str  # expected number as a string to avoid JSON float precision loss
    epsilon: float


class _CustomMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["custom"]
    value: str  # shell command; receives actual output via stdin, exits 0 for match


OutputMatch = Annotated[
    _Sha256Match | _ContainsMatch | _RegexMatch | _NumericMatch | _CustomMatch,
    Field(discriminator="mode"),
]


class ExpectedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: OutputSource
    match: OutputMatch


class Experiment(BaseModel):
    """Experiment metadata attached to a REE draft."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str = ""
    command: str = ""
    outputs: list[ExpectedOutput] = Field(default_factory=list)
