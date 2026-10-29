from __future__ import annotations

from enum import Enum, StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from repo2ree_ree.dependency import Dependency


class ThreatCategory(StrEnum):
    DEPENDENCY = "dependency"
    ENVIRONMENT = "environment"
    MACHINE = "machine"


class DependencyLevel(int, Enum):
    NONE = 0
    DECLARED = 1
    PINNED = 2
    LOCKED = 3

    @property
    def label(self) -> str:
        return {0: "None", 1: "Declared", 2: "Pinned", 3: "Locked"}[self.value]


class EnvironmentLevel(int, Enum):
    NONE = 0
    CONTAINER = 1
    DECLARATIVE = 2

    @property
    def label(self) -> str:
        return {0: "None", 1: "Container", 2: "Declarative"}[self.value]


class MachineLevel(int, Enum):
    NONE = 0
    VM = 1

    @property
    def label(self) -> str:
        return {0: "None", 1: "Virtual machine"}[self.value]


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
}


class Threat(BaseModel):
    id: str
    category: ThreatCategory
    severity: Severity
    blocking: bool = False
    title: str
    detail: str
    remediation: str
    affected: list[str] = Field(default_factory=list)


class DependencySummary(BaseModel):
    manifests: int = 0
    total: int = 0
    pinned: int = 0
    ranged: int = 0
    unpinned: int = 0
    locked: int = 0


DependencyStatus = Literal["locked", "pinned", "ranged", "unpinned", "undeclared"]

RuntimePresence = Literal["observed", "version-mismatch", "not-observed"]


class EvaluatedDependency(Dependency):
    status: DependencyStatus
    runtime_presence: RuntimePresence | None = None


class UndeclaredPackage(BaseModel):
    ecosystem: str
    name: str
    version: str | None = None


class SbomCrossCheckSummary(BaseModel):
    sbom_digest: str | None = None
    checked_at: str = ""
    declared_direct_total: int = 0
    observed_matched: int = 0
    version_mismatches: int = 0
    undeclared_same_ecosystem: int = 0
    observed_total: int = 0
    undeclared: list[UndeclaredPackage] = Field(default_factory=list)


class ReproducibilityReport(BaseModel):
    dependency_level: DependencyLevel
    environment_level: EnvironmentLevel
    machine_level: MachineLevel
    dependency_summary: DependencySummary
    dependencies: list[EvaluatedDependency] = Field(default_factory=list)
    sbom_cross_check: SbomCrossCheckSummary | None = None
    threats: list[Threat]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dependency_level_label(self) -> str:
        return self.dependency_level.label

    @computed_field  # type: ignore[prop-decorator]
    @property
    def environment_level_label(self) -> str:
        return self.environment_level.label

    @computed_field  # type: ignore[prop-decorator]
    @property
    def machine_level_label(self) -> str:
        return self.machine_level.label

    @computed_field  # type: ignore[prop-decorator]
    @property
    def detected_dependencies(self) -> str:
        total = self.dependency_summary.total
        manifests = self.dependency_summary.manifests
        return (
            f"{total} dependenc{'y' if total == 1 else 'ies'} across "
            f"{manifests} manifest file{'s' if manifests != 1 else ''}"
        )
