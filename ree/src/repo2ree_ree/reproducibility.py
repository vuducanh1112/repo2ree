from __future__ import annotations

from enum import Enum, StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from repo2ree_ree.dependency import Dependency


class ThreatCategory(StrEnum):
    # Independent reproducibility dimensions, each scored on its own axis rather
    # than a single linear ladder. Dependency declaration (what software is
    # installed), environment capture (the container / declarative software
    # stack), and machine capture (a VM pinning the whole machine + OS) are
    # orthogonal — the ideal setup is a VM *and* a container/Nix environment.
    DEPENDENCY = "dependency"
    ENVIRONMENT = "environment"
    MACHINE = "machine"


class DependencyLevel(int, Enum):
    NONE = 0  # no manifest
    DECLARED = 1  # manifest, but unpinned / range-only
    PINNED = 2  # exact top-level pins
    LOCKED = 3  # lockfile present

    @property
    def label(self) -> str:
        return {0: "None", 1: "Declared", 2: "Pinned", 3: "Locked"}[self.value]


class EnvironmentLevel(int, Enum):
    NONE = 0  # no container / Nix
    CONTAINER = 1  # container image, but not declarative
    DECLARATIVE = 2  # declarative system spec (e.g. Nix)

    @property
    def label(self) -> str:
        return {0: "None", 1: "Container", 2: "Declarative"}[self.value]


class MachineLevel(int, Enum):
    NONE = 0  # no VM image
    VM = 1  # a virtual machine image / definition is provided

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


# Per-dependency reproducibility rung. ``locked`` means a lockfile resolved it;
# ``pinned``/``ranged``/``unpinned`` classify the declared constraint;
# ``undeclared`` marks an SBOM-only row the cross-check found in the runtime
# with no manifest declaring it (always ``direct=False``, so it stays out of
# the declaration summary buckets).
DependencyStatus = Literal["locked", "pinned", "ranged", "unpinned", "undeclared"]

# Verdict of the runtime-SBOM cross-check for a declared row. ``None`` until a
# cross-check ran. ``not-observed`` is not a defect: dev- and build-only
# dependencies legitimately never reach the runtime.
RuntimePresence = Literal["observed", "version-mismatch", "not-observed"]


class EvaluatedDependency(Dependency):
    """A ``Dependency`` row plus the report's classification of it.

    The status is computed here — the single classifier that also feeds the
    summary buckets — so presentation layers never re-derive it. The same
    holds for ``runtime_presence``, filled by the SBOM cross-check step.
    """

    status: DependencyStatus
    runtime_presence: RuntimePresence | None = None


class UndeclaredPackage(BaseModel):
    """One runtime package no manifest declared (same-ecosystem only)."""

    ecosystem: str
    name: str
    version: str | None = None


class SbomCrossCheckSummary(BaseModel):
    """Aggregates of the runtime-SBOM cross-check, mirrored into the receipt.

    ``undeclared`` is capped (the counts carry the truth) and holds only
    ecosystems the declared inventory uses — base-image OS packages are
    counted in ``observed_total`` but never listed.
    """

    sbom_digest: str | None = None
    checked_at: str = ""
    declared_direct_total: int = 0
    observed_matched: int = 0
    version_mismatches: int = 0
    undeclared_same_ecosystem: int = 0
    observed_total: int = 0
    undeclared: list[UndeclaredPackage] = Field(default_factory=list)


class ReproducibilityReport(BaseModel):
    # Three orthogonal axes — the model evaluate actually reasons about. The levels
    # are int-enums, so they serialize to their integer value on the wire.
    dependency_level: DependencyLevel
    environment_level: EnvironmentLevel
    machine_level: MachineLevel
    dependency_summary: DependencySummary
    # The normalized backend inventory is the sole data source for dependency
    # presentation.  It includes lock-only closure rows and OCI images so later
    # report consumers can choose their own view without re-parsing manifests.
    dependencies: list[EvaluatedDependency] = Field(default_factory=list)
    # Filled by the cross_check_sbom step, which rewrites the report artifact;
    # ``None`` until a cross-check ran (and again after evaluate re-runs).
    sbom_cross_check: SbomCrossCheckSummary | None = None
    threats: list[Threat]

    # Labels are derived from their level, never set independently, so they can
    # never drift out of sync. They are still serialized (computed fields) so the
    # wire contract keeps `dependency_level_label` etc.
    # mypy does not support decorators on properties (python/mypy#1362), so the
    # @computed_field lines need an explicit ignore.
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
