from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.model import ExperimentDefinition


class ArtifactFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exists: bool = False
    is_file: bool = False
    size: int = 0
    digest: str | None = None


@runtime_checkable
class ArtifactAccessor(Protocol):
    def stat(self, rel_path: str) -> ArtifactFile: ...

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None: ...

    def open(self, rel_path: str) -> BinaryIO | None: ...


class _NullAccessor:
    def stat(self, rel_path: str) -> ArtifactFile:
        return ArtifactFile()

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None:
        return None

    def open(self, rel_path: str) -> BinaryIO | None:
        return None


class ExperimentEnvironmentInputs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    declared_experiment_environment_path: str | None = None
    experiments: list[ExperimentDefinition] = Field(default_factory=list)
    accessor: ArtifactAccessor = Field(default_factory=_NullAccessor)

    def experiment(self, name: str) -> ExperimentDefinition | None:
        for experiment in self.experiments:
            if experiment.name == name:
                return experiment
        return None
