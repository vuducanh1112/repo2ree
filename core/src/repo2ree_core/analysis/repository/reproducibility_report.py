from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from repo2ree_ree.dependency import Dependency, DependencyInventory
from repo2ree_ree.reproducibility import (
    _SEVERITY_RANK,
    DependencyLevel,
    DependencyStatus,
    DependencySummary,
    EnvironmentLevel,
    EvaluatedDependency,
    MachineLevel,
    ReproducibilityReport,
    Severity,
    Threat,
    ThreatCategory,
)


class FileSignals(BaseModel):
    has_manifest: bool = False
    has_dockerfile: bool = False
    has_nix_file: bool = False
    has_vm: bool = False
    dockerfile_texts: list[str] = Field(default_factory=list)


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


_RANGE_TOKENS = ("<", ">", "~", "^", "*", "||", ",")

_WILDCARD_COMPONENT_RE = re.compile(r"(?:^|\.)[xX*](?:\.|$)")

_EXACT_VERSION_RE = re.compile(r"^[0-9][A-Za-z0-9._+\-]*$")


def _classify(version: str | None) -> DependencyStatus:
    if not version or not version.strip():
        return "unpinned"
    normalized = version.strip()
    if normalized.startswith("=="):
        return "ranged" if _WILDCARD_COMPONENT_RE.search(normalized[2:]) else "pinned"
    body = normalized[1:].strip() if normalized.startswith("=") else normalized
    if (
        not any(token in body for token in _RANGE_TOKENS)
        and _EXACT_VERSION_RE.match(body)
        and not _WILDCARD_COMPONENT_RE.search(body)
    ):
        return "pinned"
    return "ranged"


def _dependency_status(dep: Dependency) -> DependencyStatus:
    return "locked" if dep.locked_version else _classify(dep.declared_constraint)


def _dep_label(dep: Dependency) -> str:
    return f"{dep.name} {dep.declared_constraint}".strip() if dep.declared_constraint else dep.name


def _apt_install_is_unpinned(dockerfile_text: str) -> bool:
    for raw in dockerfile_text.splitlines():
        line = raw.strip()
        if re.search(r"\bapt(?:-get)?\s+install\b", line) and "=" not in re.sub(r"--[a-z-]+", "", line):
            return True
    return False


def _summarize_dependencies(inventory: DependencyInventory) -> DependencySummary:
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
    if summary.total == 0 and summary.manifests == 0:
        return DependencyLevel.NONE
    if summary.total > 0 and summary.locked == summary.total:
        return DependencyLevel.LOCKED
    if summary.pinned > 0 or summary.locked > 0:
        return DependencyLevel.PINNED
    return DependencyLevel.DECLARED


def _environment_level(file_signals: FileSignals) -> EnvironmentLevel:
    if file_signals.has_nix_file:
        return EnvironmentLevel.DECLARATIVE
    if file_signals.has_dockerfile:
        return EnvironmentLevel.CONTAINER
    return EnvironmentLevel.NONE


def _machine_level(file_signals: FileSignals) -> MachineLevel:
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


def build_report(
    inventory: DependencyInventory | None,
    file_signals: FileSignals,
) -> ReproducibilityReport:
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
