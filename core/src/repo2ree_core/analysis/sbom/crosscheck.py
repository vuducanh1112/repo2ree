from __future__ import annotations

from dataclasses import dataclass

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage
from repo2ree_core.analysis.sbom.versions import versions_match
from repo2ree_ree.dependency import Dependency, Ecosystem
from repo2ree_ree.reproducibility import (
    EvaluatedDependency,
    ExperimentEnvironmentPresence,
    SbomCrossCheckSummary,
    UndeclaredPackage,
)


@dataclass(frozen=True)
class CrossCheckResult:
    dependencies: list[EvaluatedDependency]
    summary: SbomCrossCheckSummary


def cross_check(
    dependencies: list[EvaluatedDependency],
    observed: list[ObservedPackage],
) -> CrossCheckResult:
    by_key: dict[tuple[Ecosystem, str], ObservedPackage] = {}
    for package in observed:
        by_key.setdefault((package.ecosystem, package.name), package)

    inventory_keys = {(dep.ecosystem, dep.name) for dep in dependencies}
    declared_ecosystems = {dep.ecosystem for dep in dependencies if dep.ecosystem not in ("oci", "other")}

    merged: list[EvaluatedDependency] = []
    direct_total = 0
    matched = 0
    mismatched = 0
    for dep in dependencies:
        if dep.ecosystem == "oci":
            merged.append(dep)
            continue
        match = by_key.get((dep.ecosystem, dep.name))
        presence = _presence(dep, match)
        merged.append(
            dep.model_copy(
                update={
                    "observed_version": match.version if match else None,
                    "experiment_environment_presence": presence,
                }
            )
        )
        if dep.direct:
            direct_total += 1
            if presence == "observed":
                matched += 1
            elif presence == "version-mismatch":
                mismatched += 1

    undeclared = sorted(
        (
            package
            for key, package in by_key.items()
            if package.ecosystem in declared_ecosystems and key not in inventory_keys
        ),
        key=lambda package: (package.ecosystem, package.name),
    )
    merged.extend(
        EvaluatedDependency(
            ecosystem=package.ecosystem,
            name=package.name,
            direct=False,
            status="undeclared",
            observed_version=package.version,
        )
        for package in undeclared
    )

    summary = SbomCrossCheckSummary(
        declared_direct_total=direct_total,
        observed_matched=matched,
        version_mismatches=mismatched,
        undeclared_same_ecosystem=len(undeclared),
        observed_total=len(observed),
        undeclared=[
            UndeclaredPackage(ecosystem=package.ecosystem, name=package.name, version=package.version)
            for package in undeclared
        ],
    )
    return CrossCheckResult(dependencies=merged, summary=summary)


def _presence(dep: Dependency, package: ObservedPackage | None) -> ExperimentEnvironmentPresence:
    if package is None:
        return "not-observed"
    expected = _expected_version(dep)
    if expected and package.version and not versions_match(expected, package.version):
        return "version-mismatch"
    return "observed"


def _expected_version(dep: Dependency) -> str | None:
    if dep.locked_version:
        return dep.locked_version
    constraint = (dep.declared_constraint or "").strip()
    if constraint.startswith("=="):
        body = constraint[2:].strip()
    elif constraint.startswith("=") and not constraint.startswith(("=<", "=>")):
        body = constraint[1:].strip()
    else:
        return None
    if not body or any(token in body for token in ("*", ",", " ")):
        return None
    return body
