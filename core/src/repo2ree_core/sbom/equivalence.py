"""SBOM closure equivalence: does a reproduced runtime carry the same packages?

The observed-vs-observed counterpart of :mod:`repo2ree_core.sbom.crosscheck`.
The cross-check asks whether the runtime honours what the author *declared*;
this module asks whether a reviewer's freshly built runtime carries the same
dependency closure as the author's — the certifiable property when a container
build is not bit-reproducible, which is the ordinary case.

Why the closure and not the bytes: image builds embed timestamps, layer
ordering, and base-image tags that move, so identical inputs routinely produce
different digests while installing exactly the same software. A digest match is
therefore the *stronger* verdict, not the only acceptable one, and a closure
match is what a reviewer can realistically certify.

The ``other`` ecosystem is advisory, never decisive. ``parse_cyclonedx`` maps
every unlisted purl type (apk, rpm, golang, ...) onto that single bucket keyed
by name alone, so two genuinely different packages can collide there. Letting a
bucket that cannot distinguish its members decide a verdict would manufacture
both false differences and false equivalences; its deltas are counted and
reported so a reviewer still sees them.

Pure module: values in, values out, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from repo2ree_core.domain.dependency import Ecosystem
from repo2ree_core.sbom.cyclonedx import ObservedPackage
from repo2ree_core.sbom.versions import versions_match

ClosureVerdict = Literal["equivalent", "different", "inconclusive"]

# Listed deltas are capped so a pathological image cannot balloon the record;
# the counts carry the truth. Mirrors the cross-check's cap for the same reason.
DELTA_LIST_CAP = 50

# The bucket that cannot distinguish its own members (see the module docstring).
_ADVISORY_ECOSYSTEM: Ecosystem = "other"


@dataclass(frozen=True)
class PackageDelta:
    """One package the two closures disagree about."""

    ecosystem: Ecosystem
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


@dataclass(frozen=True)
class ClosureDelta:
    """The full disagreement between two dependency closures.

    ``missing`` is present for the author and absent for the reviewer;
    ``extra`` is the reverse. Deltas are split into the decisive rows (which
    settle the verdict) and the advisory ``other``-ecosystem rows. The ``*_count``
    fields are the truth; the lists beside them are capped samples.
    """

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
        """How many deltas actually bear on the verdict."""
        return self.missing_count + self.extra_count + self.version_mismatch_count


def compare_sbom_closures(
    expected: list[ObservedPackage],
    observed: list[ObservedPackage],
) -> ClosureDelta:
    """Diff the author's runtime closure against a reviewer's rebuilt one.

    Packages are joined on ``(ecosystem, name)`` — the identity the CycloneDX
    adapter already normalizes both sides to — and versions are compared with
    the shared normalization, so an epoch or a ``v`` prefix is never mistaken
    for a rebuild difference.
    """
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
        missing=_capped(missing),
        extra=_capped(extra),
        version_mismatches=_capped(mismatched),
        advisory=_capped(advisory),
    )


def closure_verdict(delta: ClosureDelta) -> ClosureVerdict:
    """The verdict a closure delta settles on.

    ``inconclusive`` when either side produced no packages at all: an empty
    closure means the scan or the author baseline is absent, and "nothing
    differs from nothing" is not evidence of a faithful rebuild.
    """
    if delta.expected_total == 0 or delta.observed_total == 0:
        return "inconclusive"
    return "equivalent" if delta.decisive_count == 0 else "different"


def _by_key(packages: list[ObservedPackage]) -> dict[tuple[Ecosystem, str], ObservedPackage]:
    """First occurrence per identity — an SBOM may list a package more than once."""
    table: dict[tuple[Ecosystem, str], ObservedPackage] = {}
    for package in packages:
        table.setdefault((package.ecosystem, package.name), package)
    return table


def _same_version(expected: str | None, observed: str | None) -> bool:
    """Whether two recorded versions agree, treating an unrecorded one as agreeing.

    Only a version *both* sides state can disagree: a component the scanner
    could not version on one side is missing metadata, not a rebuild difference.
    """
    if not expected or not observed:
        return True
    return versions_match(expected, observed)


def _route(advisory: list[PackageDelta], decisive: list[PackageDelta], delta: PackageDelta) -> None:
    """File a delta as advisory or decisive, by the ecosystem that produced it."""
    (advisory if delta.ecosystem == _ADVISORY_ECOSYSTEM else decisive).append(delta)


def _capped(deltas: list[PackageDelta]) -> list[PackageDelta]:
    return sorted(deltas, key=lambda delta: (delta.ecosystem, delta.name))[:DELTA_LIST_CAP]
