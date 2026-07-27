from __future__ import annotations

from repo2ree_core.analysis.sbom.cyclonedx import ObservedPackage
from repo2ree_core.analysis.sbom.equivalence import (
    DELTA_LIST_CAP,
    closure_verdict,
    compare_sbom_closures,
)


def _pkg(name: str, version: str | None = "1.0.0", ecosystem: str = "pypi") -> ObservedPackage:
    return ObservedPackage(ecosystem=ecosystem, name=name, version=version)  # type: ignore[arg-type]


def test_same_closure_is_equivalent() -> None:
    author = [_pkg("numpy", "1.26.4"), _pkg("requests", "2.31.0")]
    reviewer = [_pkg("requests", "2.31.0"), _pkg("numpy", "1.26.4")]

    delta = compare_sbom_closures(author, reviewer)

    assert delta.matched == 2
    assert delta.decisive_count == 0
    assert closure_verdict(delta) == "equivalent"


def test_version_drift_is_a_difference() -> None:
    delta = compare_sbom_closures([_pkg("numpy", "1.26.4")], [_pkg("numpy", "2.0.0")])

    assert delta.version_mismatch_count == 1
    assert delta.version_mismatches[0].expected_version == "1.26.4"
    assert delta.version_mismatches[0].observed_version == "2.0.0"
    assert closure_verdict(delta) == "different"


def test_missing_and_extra_packages_are_named_on_the_right_side() -> None:
    delta = compare_sbom_closures([_pkg("numpy")], [_pkg("scipy")])

    assert [row.name for row in delta.missing] == ["numpy"]
    assert [row.name for row in delta.extra] == ["scipy"]
    assert closure_verdict(delta) == "different"


def test_epoch_and_v_prefix_are_packaging_metadata_not_drift() -> None:
    author = [_pkg("libc-bin", "2:2.36-9", ecosystem="apt"), _pkg("cli", "v1.2.3")]
    reviewer = [_pkg("libc-bin", "2.36-9", ecosystem="apt"), _pkg("cli", "1.2.3")]

    delta = compare_sbom_closures(author, reviewer)

    assert delta.matched == 2
    assert closure_verdict(delta) == "equivalent"


def test_a_component_only_one_side_versions_is_not_drift() -> None:
    delta = compare_sbom_closures([_pkg("numpy", None)], [_pkg("numpy", "1.26.4")])

    assert delta.matched == 1
    assert closure_verdict(delta) == "equivalent"


def test_other_ecosystem_deltas_are_advisory_never_decisive() -> None:
    # ``other`` collapses distinct purl types onto the name alone, so it cannot
    # tell its own members apart and must not settle a verdict.
    author = [_pkg("numpy"), _pkg("busybox", "1.36", ecosystem="other")]
    reviewer = [_pkg("numpy"), _pkg("busybox", "1.37", ecosystem="other")]

    delta = compare_sbom_closures(author, reviewer)

    assert delta.advisory_count == 1
    assert delta.advisory[0].name == "busybox"
    assert delta.version_mismatch_count == 0
    assert closure_verdict(delta) == "equivalent"


def test_an_empty_side_is_inconclusive_not_equivalent() -> None:
    assert closure_verdict(compare_sbom_closures([], [_pkg("numpy")])) == "inconclusive"
    assert closure_verdict(compare_sbom_closures([_pkg("numpy")], [])) == "inconclusive"
    assert closure_verdict(compare_sbom_closures([], [])) == "inconclusive"


def test_delta_lists_are_capped_but_the_counts_are_whole() -> None:
    author = [_pkg(f"pkg-{index:03d}") for index in range(DELTA_LIST_CAP + 20)]

    delta = compare_sbom_closures(author, [])

    assert delta.missing_count == DELTA_LIST_CAP + 20
    assert len(delta.missing) == DELTA_LIST_CAP
    # Inconclusive here (the reviewer side is empty), but the delta still records
    # everything the comparison saw.
    assert delta.expected_total == DELTA_LIST_CAP + 20


def test_a_package_listed_twice_joins_once() -> None:
    delta = compare_sbom_closures([_pkg("numpy"), _pkg("numpy")], [_pkg("numpy")])

    assert delta.expected_total == 1
    assert delta.matched == 1
    assert closure_verdict(delta) == "equivalent"
