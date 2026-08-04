"""Reproducibility threat report.

Pure analysis layer: turns a ``DependencyInventory`` plus a set of workspace
file signals into a structured report that enumerates concrete threats to
reproducibility (unpinned dependencies, missing lockfile, floating base image,
non-declarative system, ...).

No I/O and no subprocess: scanning the repository and serializing the report to
``artifacts/`` live in the ``evaluate_dependency_score`` handler.  This module
only computes.

This report reads repository manifests, lockfiles, and environment declarations
and grades how well the repository declares what it needs. The author handler
binds its bounded conclusions and payload digest into an
``EvaluateReproducibilityReceipt``; overall REE evidence status is derived
separately by ``domain.ree.audit``.

Functions carry design-by-contract assertions (pre-/post-conditions) for the
invariants that the type system cannot express.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from repo2ree_core.domain.dependency import Dependency, DependencyInventory

# ================================================
# Data models
# ================================================


class ThreatCategory(str, Enum):
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


class Severity(str, Enum):
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


class FileSignals(BaseModel):
    """Filesystem-derived signals, gathered by the caller from the workspace."""

    has_manifest: bool = False
    has_dockerfile: bool = False
    has_nix_file: bool = False
    has_vm: bool = False
    # Raw text of any Dockerfiles, used for the apt-pinning heuristic.
    dockerfile_texts: list[str] = Field(default_factory=list)


# ================================================
# Filename classifiers and other pure helpers
# ================================================

# Only formats the scan registry actually parses may count as manifests: a
# name here without a parser would score DECLARED while showing no data and
# suppressing the no-manifest threat (Pipfile used to do exactly that).
_MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "package.json",
    }
)

_VM_IMAGE_SUFFIXES = (".ova", ".ovf", ".qcow2", ".vmdk", ".vdi", ".box")


def is_manifest_filename(lower_name: str) -> bool:
    return lower_name in _MANIFEST_NAMES or bool(re.match(r"^requirements[-_].+\.txt$", lower_name))


def is_dockerfile_filename(lower_name: str) -> bool:
    return lower_name in {
        "dockerfile",
        "containerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    } or lower_name.startswith(("dockerfile.", "containerfile."))


def is_vm_artifact_filename(lower_name: str) -> bool:
    return (
        lower_name == "vagrantfile"
        or lower_name.endswith((".pkr.hcl", ".pkr.json"))
        or lower_name.endswith(_VM_IMAGE_SUFFIXES)
    )


# ================================================
# Threat catalog
# ================================================

# Static copy: title / detail / remediation per threat id. The `affected` list and
# `blocking` flag are filled in at detection time.
_CATALOG: dict[str, dict[str, Any]] = {
    "no-manifest": {
        "category": ThreatCategory.DEPENDENCY,
        "severity": Severity.HIGH,
        "title": "No dependency manifest",
        "detail": "No requirements.txt, pyproject.toml, environment.yml or similar "
        "manifest was found, so the dependency set is undefined.",
        "remediation": "Create a formal dependency file (e.g. requirements.txt).",
    },
    "unpinned-deps": {
        "category": ThreatCategory.DEPENDENCY,
        "severity": Severity.HIGH,
        "title": "Unpinned dependencies",
        "detail": "Some dependencies are declared without any version. Installs "
        "resolve to whatever is newest on the day they run.",
        "remediation": "Pin required versions (e.g. pandas==2.1.0).",
    },
    "range-pins": {
        "category": ThreatCategory.DEPENDENCY,
        "severity": Severity.MEDIUM,
        "title": "Range-pinned dependencies",
        "detail": "Some dependencies use version ranges (>=, ~=, ^). Minor and "
        "patch versions can drift between installs.",
        "remediation": "Pin exact versions, then capture a lockfile.",
    },
    "no-lockfile": {
        "category": ThreatCategory.DEPENDENCY,
        "severity": Severity.MEDIUM,
        "title": "No lockfile",
        "detail": "Top-level dependencies are pinned but no lockfile was found, so "
        "transitive dependencies still float.",
        "remediation": "Use a lockfile (e.g. poetry.lock, uv.lock).",
    },
    "floating-base-image": {
        "category": ThreatCategory.ENVIRONMENT,
        "severity": Severity.HIGH,
        "title": "Floating base image",
        "detail": "A container base image is referenced without a content digest, "
        "so the same tag can resolve to different images over time.",
        "remediation": "Pin base images by digest (FROM image:tag@sha256:...).",
    },
    "unpinned-apt": {
        "category": ThreatCategory.ENVIRONMENT,
        "severity": Severity.MEDIUM,
        "title": "Unpinned system packages",
        "detail": "A Dockerfile installs apt packages without version constraints, "
        "so system libraries can change between builds.",
        "remediation": "Pin apt package versions (apt-get install pkg=version).",
    },
    "no-container": {
        "category": ThreatCategory.ENVIRONMENT,
        "severity": Severity.LOW,
        "title": "No container environment",
        "detail": "No container or declarative environment is provided, so system "
        "libraries (glibc, BLAS, CUDA) are not captured.",
        "remediation": "Add a container image (Dockerfile).",
    },
    "no-nix": {
        "category": ThreatCategory.ENVIRONMENT,
        "severity": Severity.LOW,
        "title": "Non-declarative system environment",
        "detail": "A container exists but the base image and apt steps are not "
        "declarative, so the system environment is only approximately reproducible.",
        "remediation": "Use a declarative system spec (e.g. Nix).",
    },
    "no-vm": {
        "category": ThreatCategory.MACHINE,
        "severity": Severity.LOW,
        "title": "No virtual machine",
        "detail": "No VM image is provided. A VM pins the whole machine and OS — the "
        "strongest complement to a container or Nix environment.",
        "remediation": "Provide a VM image (e.g. an OVA, qcow2, or Vagrantfile).",
    },
}

# Per axis, the threat ids (in priority order) that gate the step to the next
# level on that axis. The first one actually present becomes `blocking` — so each
# axis surfaces at most one blocking threat.
_DEP_GATE: dict[DependencyLevel, tuple[str, ...]] = {
    DependencyLevel.NONE: ("no-manifest",),
    DependencyLevel.DECLARED: ("unpinned-deps", "range-pins"),
    DependencyLevel.PINNED: ("no-lockfile",),
    DependencyLevel.LOCKED: (),
}
_ENV_GATE: dict[EnvironmentLevel, tuple[str, ...]] = {
    EnvironmentLevel.NONE: ("no-container",),
    EnvironmentLevel.CONTAINER: ("no-nix", "floating-base-image", "unpinned-apt"),
    EnvironmentLevel.DECLARATIVE: (),
}
_MACHINE_GATE: dict[MachineLevel, tuple[str, ...]] = {
    MachineLevel.NONE: ("no-vm",),
    MachineLevel.VM: (),
}


# ================================================
# Internals
# ================================================


_RANGE_TOKENS = ("<", ">", "~", "^", "*", "||", ",")

# A wildcard version component (1.x, 2.7.X, ==1.*) floats no matter how
# pin-shaped the rest of the string looks.
_WILDCARD_COMPONENT_RE = re.compile(r"(?:^|\.)[xX*](?:\.|$)")

_EXACT_VERSION_RE = re.compile(r"^[0-9][A-Za-z0-9._+\-]*$")


def _classify(version: str | None) -> DependencyStatus:
    """Classify a declared version string: pinned | ranged | unpinned."""
    if not version or not version.strip():
        return "unpinned"
    normalized = version.strip()
    if normalized.startswith("=="):
        # PEP 440 exact — unless the version body carries a wildcard (==1.*).
        return "ranged" if _WILDCARD_COMPONENT_RE.search(normalized[2:]) else "pinned"
    # conda (`numpy=1.21.0`) and npm (`=1.2.3`) spell exact pins with one `=`.
    body = normalized[1:].strip() if normalized.startswith("=") else normalized
    if (
        not any(token in body for token in _RANGE_TOKENS)
        and _EXACT_VERSION_RE.match(body)
        and not _WILDCARD_COMPONENT_RE.search(body)
    ):
        return "pinned"
    return "ranged"


def _dependency_status(dep: Dependency) -> DependencyStatus:
    """The single classification rule: a lockfile resolution wins, otherwise
    the declared constraint decides. Feeds both the summary buckets and the
    per-row status on the wire, so the two can never disagree."""
    return "locked" if dep.locked_version else _classify(dep.declared_constraint)


def _dep_label(dep: Dependency) -> str:
    return f"{dep.name} {dep.declared_constraint}".strip() if dep.declared_constraint else dep.name


def _apt_install_is_unpinned(dockerfile_text: str) -> bool:
    """Heuristic: a Dockerfile apt(-get) install without any `pkg=version` pin."""
    for raw in dockerfile_text.splitlines():
        line = raw.strip()
        # A pinned install names a version with `pkg=ver`.
        if re.search(r"\bapt(?:-get)?\s+install\b", line) and "=" not in re.sub(r"--[a-z-]+", "", line):
            return True
    return False


def _summarize_dependencies(inventory: DependencyInventory) -> DependencySummary:
    """Per-dependency inventory over the *direct* library dependencies —
    transitive lockfile closure rows and container image references are the
    other axes' business."""
    library_deps = [d for d in inventory.dependencies if d.ecosystem != "oci" and d.direct]
    manifests = {d.declared_in for d in library_deps if d.declared_in}
    summary = DependencySummary(manifests=len(manifests))
    for dep in library_deps:
        summary.total += 1
        status = _dependency_status(dep)
        if status == "locked":
            summary.locked += 1
        elif status == "pinned":
            summary.pinned += 1
        elif status == "ranged":
            summary.ranged += 1
        else:
            summary.unpinned += 1

    if summary.total != (summary.pinned + summary.ranged + summary.unpinned + summary.locked):
        raise AssertionError("dependency summary buckets must partition the total")

    return summary


def _dependency_level(summary: DependencySummary) -> DependencyLevel:
    """Maturity of dependency *declaration*, independent of the environment."""
    if summary.total == 0 and summary.manifests == 0:
        return DependencyLevel.NONE
    if summary.total > 0 and summary.locked == summary.total:
        return DependencyLevel.LOCKED
    if summary.pinned > 0 or summary.locked > 0:
        return DependencyLevel.PINNED
    return DependencyLevel.DECLARED


def _environment_level(file_signals: FileSignals) -> EnvironmentLevel:
    """Maturity of the software-stack *capture* (container / declarative)."""
    if file_signals.has_nix_file:
        return EnvironmentLevel.DECLARATIVE
    if file_signals.has_dockerfile:
        return EnvironmentLevel.CONTAINER
    return EnvironmentLevel.NONE


def _machine_level(file_signals: FileSignals) -> MachineLevel:
    """Whether the whole machine/OS is pinned by a VM image — orthogonal to the
    container/declarative environment axis (the ideal is a VM *and* a container)."""
    return MachineLevel.VM if file_signals.has_vm else MachineLevel.NONE


def _make_threat(threat_id: str, affected: list[str] | None = None) -> Threat:
    if threat_id not in _CATALOG:
        raise AssertionError(f"unknown threat id: {threat_id!r}")
    spec = _CATALOG[threat_id]
    return Threat(
        id=threat_id,
        category=spec["category"],
        severity=spec["severity"],
        title=spec["title"],
        detail=spec["detail"],
        remediation=spec["remediation"],
        affected=affected or [],
    )


def _detect_threats(
    inventory: DependencyInventory,
    summary: DependencySummary,
    file_signals: FileSignals,
) -> list[Threat]:
    threats: list[Threat] = []
    library_deps = [d for d in inventory.dependencies if d.ecosystem != "oci" and d.direct]
    container_deps = [d for d in inventory.dependencies if d.ecosystem == "oci"]

    # --- Dependency category ---
    if summary.manifests == 0 and summary.total == 0:
        threats.append(_make_threat("no-manifest"))
    else:
        unpinned = [_dep_label(d) for d in library_deps if _dependency_status(d) == "unpinned"]
        ranged = [_dep_label(d) for d in library_deps if _dependency_status(d) == "ranged"]
        if unpinned:
            threats.append(_make_threat("unpinned-deps", unpinned))
        if ranged:
            threats.append(_make_threat("range-pins", ranged))
        if summary.pinned > 0 and summary.locked == 0:
            threats.append(_make_threat("no-lockfile"))

    # --- Environment axis ---
    if not file_signals.has_dockerfile and not file_signals.has_nix_file:
        threats.append(_make_threat("no-container"))
    else:
        floating = [_dep_label(d) for d in container_deps if not d.locked_hashes]
        if floating:
            threats.append(_make_threat("floating-base-image", floating))
        if any(_apt_install_is_unpinned(text) for text in file_signals.dockerfile_texts):
            threats.append(_make_threat("unpinned-apt"))
        if file_signals.has_dockerfile and not file_signals.has_nix_file:
            threats.append(_make_threat("no-nix"))

    # --- Machine axis ---
    if not file_signals.has_vm:
        threats.append(_make_threat("no-vm"))

    ids = [threat.id for threat in threats]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate threat ids emitted")
    if not all(threat_id in _CATALOG for threat_id in ids):
        raise AssertionError("unknown threat id")

    return threats


def _rank_and_mark(
    threats: list[Threat],
    dependency_level: DependencyLevel,
    environment_level: EnvironmentLevel,
    machine_level: MachineLevel,
) -> list[Threat]:
    """Mark the threat that gates the next level on each axis (if present) and sort
    so blocking threats come first, then by descending severity."""
    present = {threat.id: threat for threat in threats}
    for gate in (
        _DEP_GATE.get(dependency_level, ()),
        _ENV_GATE.get(environment_level, ()),
        _MACHINE_GATE.get(machine_level, ()),
    ):
        for candidate in gate:
            if candidate in present:
                present[candidate].blocking = True
                break

    ordered = sorted(
        threats,
        key=lambda threat: (not threat.blocking, _SEVERITY_RANK[threat.severity]),
    )

    blocking_per_dimension: dict[ThreatCategory, int] = {}
    for threat in ordered:
        if threat.blocking:
            blocking_per_dimension[threat.category] = blocking_per_dimension.get(threat.category, 0) + 1
    if not all(count <= 1 for count in blocking_per_dimension.values()):
        raise AssertionError("at most one blocking threat per dimension")
    if len(ordered) != len(threats):
        raise AssertionError("ranking must not drop threats")

    return ordered


# ================================================
# Entry point
# ================================================


def build_report(
    inventory: DependencyInventory | None,
    file_signals: FileSignals,
) -> ReproducibilityReport:
    """Build the reproducibility threat report from a dependency inventory and
    workspace file signals."""

    if inventory is None:
        inventory = DependencyInventory()
    summary = _summarize_dependencies(inventory)
    if summary.manifests == 0 and summary.total == 0 and file_signals.has_manifest:
        summary.manifests = 1
    dependency_level = _dependency_level(summary)
    environment_level = _environment_level(file_signals)
    machine_level = _machine_level(file_signals)
    threats = _rank_and_mark(
        _detect_threats(inventory, summary, file_signals),
        dependency_level,
        environment_level,
        machine_level,
    )

    report = ReproducibilityReport(
        dependency_level=dependency_level,
        environment_level=environment_level,
        machine_level=machine_level,
        dependency_summary=summary,
        dependencies=[
            EvaluatedDependency(**dep.model_dump(), status=_dependency_status(dep)) for dep in inventory.dependencies
        ],
        threats=threats,
    )

    if not all(threat.id in _CATALOG for threat in report.threats):
        raise AssertionError("report contains unknown threat id")

    return report
