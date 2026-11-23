from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage
from repo2ree_core.analysis.sbom.versions import versions_match
from repo2ree_ree.dependency import Ecosystem

ClosureVerdict = Literal["equivalent", "different", "inconclusive"]

_ADVISORY_ECOSYSTEM: Ecosystem = "other"


@dataclass(frozen=True)
class PackageDelta:
    ecosystem: Ecosystem
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


@dataclass(frozen=True)
class ClosureDelta:
    expected_total: int = 0
    observed_total: int = 0
    matched: int = 0
    missing_count: int = 0
    extra_count: int = 0
    version_mismatch_count: int = 0
    advisory_count: int = 0
    missing: list[PackageDelta] = field(default_factory=list)
    extra: list[PackageDelta] = field(default_factory=list)
    version_mismatches: list[PackageDelta] = field(default_factory=list)
    advisory: list[PackageDelta] = field(default_factory=list)

    @property
    def decisive_count(self) -> int:
        return self.missing_count + self.extra_count + self.version_mismatch_count


def compare_sbom_closures(
    expected: list[ObservedPackage],
    observed: list[ObservedPackage],
) -> ClosureDelta:
    expected_by_key = _by_key(expected)
    observed_by_key = _by_key(observed)

    matched = 0
    missing: list[PackageDelta] = []
    extra: list[PackageDelta] = []
    mismatched: list[PackageDelta] = []
    advisory: list[PackageDelta] = []

    for key, package in expected_by_key.items():
        counterpart = observed_by_key.get(key)
        if counterpart is None:
            _route(
                advisory,
                missing,
                PackageDelta(
                    ecosystem=package.ecosystem,
                    name=package.name,
                    expected_version=package.version,
                ),
            )
        elif _same_version(package.version, counterpart.version):
            matched += 1
        else:
            _route(
                advisory,
                mismatched,
                PackageDelta(
                    ecosystem=package.ecosystem,
                    name=package.name,
                    expected_version=package.version,
                    observed_version=counterpart.version,
                ),
            )

    for key, package in observed_by_key.items():
        if key in expected_by_key:
            continue
        _route(
            advisory,
            extra,
            PackageDelta(
                ecosystem=package.ecosystem,
                name=package.name,
                observed_version=package.version,
            ),
        )

    return ClosureDelta(
        expected_total=len(expected_by_key),
        observed_total=len(observed_by_key),
        matched=matched,
        missing_count=len(missing),
        extra_count=len(extra),
        version_mismatch_count=len(mismatched),
        advisory_count=len(advisory),
        missing=_sorted(missing),
        extra=_sorted(extra),
        version_mismatches=_sorted(mismatched),
        advisory=_sorted(advisory),
    )


def closure_verdict(delta: ClosureDelta) -> ClosureVerdict:
    if delta.expected_total == 0 or delta.observed_total == 0:
        return "inconclusive"
    return "equivalent" if delta.decisive_count == 0 else "different"


def _by_key(packages: list[ObservedPackage]) -> dict[tuple[Ecosystem, str], ObservedPackage]:
    table: dict[tuple[Ecosystem, str], ObservedPackage] = {}
    for package in packages:
        table.setdefault((package.ecosystem, package.name), package)
    return table


def _same_version(expected: str | None, observed: str | None) -> bool:
    if not expected or not observed:
        return True
    return versions_match(expected, observed)


def _route(advisory: list[PackageDelta], decisive: list[PackageDelta], delta: PackageDelta) -> None:
    (advisory if delta.ecosystem == _ADVISORY_ECOSYSTEM else decisive).append(delta)


def _sorted(deltas: list[PackageDelta]) -> list[PackageDelta]:
    return sorted(deltas, key=lambda delta: (delta.ecosystem, delta.name))
