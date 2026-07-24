"""Cross-check: which declared dependencies are actually in the runtime.

Pure merge over the IR — fills the ``observed_*`` stage on the scanned
inventory rows and adds SBOM-only rows for same-ecosystem undeclared
packages. Reading the SBOM, digesting it, and rewriting the report artifact
belong to the handler.

Verdict semantics (deliberately asymmetric):

* ``not-observed`` is surfaced, never penalized — dev- and build-only
  dependencies legitimately never reach the runtime.
* Undeclared packages are only listed for ecosystems the declared inventory
  actually uses: an unexpected pypi package is the headline signal, the base
  image's OS packages are noise (they stay in ``observed_total``).
"""

from __future__ import annotations

from dataclasses import dataclass

from repo2ree_core.domain.dependency import Dependency, Ecosystem
from repo2ree_core.repo_profiler.reproducibility_report import (
    EvaluatedDependency,
    RuntimePresence,
    SbomCrossCheckSummary,
    UndeclaredPackage,
)
from repo2ree_core.sbom.cyclonedx import ObservedPackage
from repo2ree_core.sbom.versions import versions_match

# The listed undeclared packages are capped so a pathological image cannot
# balloon the report; the count carries the truth.
_UNDECLARED_LIST_CAP = 50


@dataclass(frozen=True)
class CrossCheckResult:
    """Enriched rows plus the aggregates both the report and receipt carry."""

    dependencies: list[EvaluatedDependency]
    summary: SbomCrossCheckSummary


def cross_check(
    dependencies: list[EvaluatedDependency],
    observed: list[ObservedPackage],
) -> CrossCheckResult:
    """Merge the runtime's observed packages into the scanned inventory."""

    by_key: dict[tuple[Ecosystem, str], ObservedPackage] = {}
    for package in observed:
        by_key.setdefault((package.ecosystem, package.name), package)

    inventory_keys = {(dep.ecosystem, dep.name) for dep in dependencies}
    # Only manifest-backed ecosystems can have "undeclared" findings; ``oci``
    # rows are the image itself and ``other`` rows can never join.
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
                    "runtime_presence": presence,
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
    for package in undeclared:
        merged.append(
            EvaluatedDependency(
                ecosystem=package.ecosystem,
                name=package.name,
                direct=False,
                status="undeclared",
                observed_version=package.version,
            )
        )

    summary = SbomCrossCheckSummary(
        declared_direct_total=direct_total,
        observed_matched=matched,
        version_mismatches=mismatched,
        undeclared_same_ecosystem=len(undeclared),
        observed_total=len(observed),
        undeclared=[
            UndeclaredPackage(ecosystem=package.ecosystem, name=package.name, version=package.version)
            for package in undeclared[:_UNDECLARED_LIST_CAP]
        ],
    )
    return CrossCheckResult(dependencies=merged, summary=summary)


def _presence(dep: Dependency, package: ObservedPackage | None) -> RuntimePresence:
    if package is None:
        return "not-observed"
    expected = _expected_version(dep)
    if expected and package.version and not versions_match(expected, package.version):
        return "version-mismatch"
    return "observed"


def _expected_version(dep: Dependency) -> str | None:
    """The exact version the inventory expects, when it names one.

    A lockfile resolution wins; otherwise only an exact declared pin
    (``==1.2.3`` / ``=1.2.3``) is comparable — ranges have nothing to
    mismatch against.
    """
    if dep.locked_version:
        return dep.locked_version
    constraint = (dep.declared_constraint or "").strip()
    if constraint.startswith("=="):
        body = constraint[2:].strip()
    elif constraint.startswith("=") and not constraint.startswith(("=<", "=>")):
        body = constraint[1:].strip()
    else:
        return None
    # Wildcards and multi-clause constraints are ranges, not pins.
    if not body or any(token in body for token in ("*", ",", " ")):
        return None
    return body
