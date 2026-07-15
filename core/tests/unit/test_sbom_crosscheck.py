"""Unit coverage for the SBOM cross-check: the CycloneDX adapter and the merge.

The adapter carries the same totality obligation as the manifest parsers
(malformed input yields the rows that did parse, never an exception); the
merge's verdicts are the contract the report and receipt aggregates rely on.
"""

from __future__ import annotations

import json

from repo2ree_core.repo_profiler.reproducibility_report import EvaluatedDependency
from repo2ree_core.sbom.crosscheck import cross_check
from repo2ree_core.sbom.cyclonedx import ObservedPackage, parse_cyclonedx

# ================================================
# Adapter
# ================================================


def _doc(components: list[object]) -> str:
    return json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": components})


def test_parse_maps_purl_types_to_ecosystems() -> None:
    packages = parse_cyclonedx(
        _doc(
            [
                {"name": "Pillow", "purl": "pkg:pypi/Pillow@10.1.0"},
                {"name": "numpy", "purl": "pkg:conda/conda-forge/numpy@1.26.4"},
                {"name": "leftpad", "purl": "pkg:npm/%40scope/leftpad@1.0.0"},
                {"name": "libssl3", "purl": "pkg:deb/debian/libssl3@3.0.11-1?arch=amd64"},
                {"name": "musl", "purl": "pkg:apk/alpine/musl@1.2.4"},
            ]
        )
    )
    assert packages == [
        # pypi names are PEP 503-normalized: the join key matches the parsers'.
        ObservedPackage(ecosystem="pypi", name="pillow", version="10.1.0"),
        ObservedPackage(ecosystem="conda", name="numpy", version="1.26.4"),
        # npm keeps its (percent-decoded) scope in the name.
        ObservedPackage(ecosystem="npm", name="@scope/leftpad", version="1.0.0"),
        ObservedPackage(ecosystem="apt", name="libssl3", version="3.0.11-1"),
        # Unmapped purl types stay countable but can never join.
        ObservedPackage(ecosystem="other", name="musl", version="1.2.4"),
    ]


def test_parse_falls_back_to_component_name_without_purl() -> None:
    packages = parse_cyclonedx(_doc([{"name": "mystery", "version": "1"}]))
    assert packages == [ObservedPackage(ecosystem="other", name="mystery", version="1")]


def test_parse_is_total_over_malformed_input() -> None:
    assert parse_cyclonedx("not json") == []
    assert parse_cyclonedx("[1, 2]") == []
    assert parse_cyclonedx(json.dumps({"components": "nope"})) == []
    # A malformed component is skipped, the rest still parse.
    packages = parse_cyclonedx(_doc([42, {"purl": "pkg:pypi"}, {"name": "ok", "purl": "pkg:pypi/ok@1.0"}]))
    assert packages == [ObservedPackage(ecosystem="pypi", name="ok", version="1.0")]


# ================================================
# Merge
# ================================================


def _dep(
    name: str,
    *,
    ecosystem: str = "pypi",
    constraint: str | None = None,
    locked: str | None = None,
    direct: bool = True,
    status: str = "unpinned",
) -> EvaluatedDependency:
    return EvaluatedDependency.model_validate(
        {
            "ecosystem": ecosystem,
            "name": name,
            "declared_constraint": constraint,
            "declared_in": "requirements.txt",
            "locked_version": locked,
            "direct": direct,
            "status": status,
        }
    )


def _obs(name: str, version: str | None, *, ecosystem: str = "pypi") -> ObservedPackage:
    return ObservedPackage(ecosystem=ecosystem, name=name, version=version)  # type: ignore[arg-type]


def test_observed_fills_version_and_presence() -> None:
    result = cross_check([_dep("requests", locked="2.31.0", status="locked")], [_obs("requests", "2.31.0")])
    (row,) = result.dependencies
    assert row.observed_version == "2.31.0"
    assert row.runtime_presence == "observed"
    assert result.summary.declared_direct_total == 1
    assert result.summary.observed_matched == 1


def test_locked_version_disagreement_is_a_mismatch() -> None:
    result = cross_check([_dep("requests", locked="2.31.0", status="locked")], [_obs("requests", "2.32.0")])
    (row,) = result.dependencies
    assert row.runtime_presence == "version-mismatch"
    assert result.summary.observed_matched == 0
    assert result.summary.version_mismatches == 1


def test_range_constraints_have_nothing_to_mismatch() -> None:
    result = cross_check([_dep("requests", constraint=">=2.0", status="ranged")], [_obs("requests", "2.32.0")])
    assert result.dependencies[0].runtime_presence == "observed"


def test_exact_pin_is_compared_with_light_normalization() -> None:
    deps = [_dep("requests", constraint="==2.31.0", status="pinned")]
    assert cross_check(deps, [_obs("requests", "v2.31.0")]).dependencies[0].runtime_presence == "observed"
    # deb/conda epochs are packaging metadata, not identity.
    assert cross_check(deps, [_obs("requests", "1:2.31.0")]).dependencies[0].runtime_presence == "observed"
    assert cross_check(deps, [_obs("requests", "2.30.0")]).dependencies[0].runtime_presence == "version-mismatch"


def test_absent_dependency_is_not_observed_not_a_defect_bucket() -> None:
    result = cross_check([_dep("pytest", constraint="==8.0.0", status="pinned")], [])
    (row,) = result.dependencies
    assert row.runtime_presence == "not-observed"
    assert row.observed_version is None
    # Not observed does not count as matched, but is not a mismatch either.
    assert result.summary.version_mismatches == 0


def test_undeclared_same_ecosystem_becomes_a_row_and_is_listed() -> None:
    result = cross_check(
        [_dep("requests", locked="2.31.0", status="locked")],
        [
            _obs("requests", "2.31.0"),
            _obs("certifi", "2024.2.2"),
        ],
    )
    undeclared = [dep for dep in result.dependencies if dep.status == "undeclared"]
    (row,) = undeclared
    assert (row.name, row.observed_version, row.direct) == ("certifi", "2024.2.2", False)
    assert result.summary.undeclared_same_ecosystem == 1
    assert [pkg.name for pkg in result.summary.undeclared] == ["certifi"]


def test_other_ecosystem_packages_are_counted_but_never_listed() -> None:
    # The declared inventory is pypi-only: apt/other packages from the base
    # image are noise, not undeclared findings.
    result = cross_check(
        [_dep("requests", locked="2.31.0", status="locked")],
        [
            _obs("requests", "2.31.0"),
            _obs("libssl3", "3.0.11", ecosystem="apt"),
            _obs("musl", "1.2.4", ecosystem="other"),
        ],
    )
    assert result.summary.undeclared_same_ecosystem == 0
    assert result.summary.observed_total == 3
    assert all(dep.status != "undeclared" for dep in result.dependencies)


def test_oci_rows_pass_through_untouched() -> None:
    oci = EvaluatedDependency.model_validate(
        {"ecosystem": "oci", "name": "python", "declared_constraint": "3.12-slim", "status": "pinned"}
    )
    result = cross_check([oci], [_obs("python", "3.12")])
    assert result.dependencies[0].runtime_presence is None
    assert result.summary.declared_direct_total == 0


def test_transitive_rows_are_enriched_but_not_in_the_direct_aggregate() -> None:
    closure = _dep("urllib3", locked="2.2.0", direct=False, status="locked")
    result = cross_check([closure], [_obs("urllib3", "2.2.0")])
    assert result.dependencies[0].runtime_presence == "observed"
    assert result.summary.declared_direct_total == 0
    assert result.summary.observed_matched == 0
