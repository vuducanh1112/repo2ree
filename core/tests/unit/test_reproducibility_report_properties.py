"""Property-based checks for ``build_report``.

Two tiers:

- a sweep driving random inventories and file signals through the report's
  own design-by-contract assertions (bucket partition, one blocking threat
  per axis, catalog-only ids), plus the external invariants the assertions
  don't cover;
- metamorphic *improvement monotonicity*: applying a remediation the report
  itself recommends — pinning a dep, locking it, adding a container/nix/VM —
  must never lower the corresponding axis level. This is the score's honesty
  guarantee; note it deliberately does NOT hold for the threat *set* (pinning
  a first dep newly surfaces ``no-lockfile``), only for the level.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.domain.dependency import Dependency, DependencyInventory
from repo2ree_core.repo_profiler.reproducibility_report import _CATALOG, FileSignals, build_report

pytestmark = pytest.mark.property

_NAMES = st.sampled_from(["alpha", "beta", "gamma", "delta"])


@st.composite
def _library_row(draw) -> Dependency:
    constraint = draw(st.sampled_from([None, "==1.2.0", "1.2.0", ">=1.0", "~=2.1"]))
    locked = draw(st.booleans())
    return Dependency(
        ecosystem=draw(st.sampled_from(["pypi", "conda", "npm"])),
        name=draw(_NAMES),
        direct=draw(st.booleans()),
        declared_constraint=constraint,
        declared_in="requirements.txt",
        locked_version="9.9.9" if locked else None,
        locked_in="uv.lock" if locked else None,
    )


@st.composite
def _oci_row(draw) -> Dependency:
    return Dependency(
        ecosystem="oci",
        name=draw(_NAMES),
        declared_constraint=draw(st.sampled_from([None, "3.11", "latest"])),
        declared_in="Dockerfile",
        locked_hashes=draw(st.sampled_from([[], ["sha256:abc"]])),
    )


_INVENTORY = st.builds(
    DependencyInventory,
    dependencies=st.lists(st.one_of(_library_row(), _oci_row()), max_size=8),
)

_SIGNALS = st.builds(
    FileSignals,
    has_manifest=st.booleans(),
    has_dockerfile=st.booleans(),
    has_nix_file=st.booleans(),
    has_vm=st.booleans(),
    dockerfile_texts=st.lists(
        st.sampled_from(["FROM python:3.11", "RUN apt-get install -y curl", "RUN apt-get install -y curl=7.88-1"]),
        max_size=2,
    ),
)


class TestReportSweep:
    @given(_INVENTORY, _SIGNALS)
    def test_contracts_and_external_invariants(self, inventory: DependencyInventory, signals: FileSignals) -> None:
        # dockerfile_texts without has_dockerfile is not a state the profiler
        # can produce; keep the generated signals coherent.
        if signals.dockerfile_texts:
            signals.has_dockerfile = True

        report = build_report(inventory, signals)

        direct_libraries = [d for d in inventory.dependencies if d.ecosystem != "oci" and d.direct]
        assert report.dependency_summary.total == len(direct_libraries)
        assert all(threat.id in _CATALOG for threat in report.threats)
        # Ranking: every blocking threat precedes every non-blocking one.
        flags = [threat.blocking for threat in report.threats]
        assert flags == sorted(flags, reverse=True)
        # Levels label round-trip.
        assert report.dependency_level_label
        assert report.environment_level_label
        assert report.machine_level_label


def _pin(dep: Dependency) -> Dependency:
    return dep.model_copy(update={"declared_constraint": "==1.0.0"})


def _lock(dep: Dependency) -> Dependency:
    return dep.model_copy(update={"locked_version": "1.0.0", "locked_in": "uv.lock"})


class TestImprovementMonotonicity:
    @given(_INVENTORY, _SIGNALS, st.data())
    def test_pinning_or_locking_never_lowers_the_dependency_level(
        self, inventory: DependencyInventory, signals: FileSignals, data: st.DataObject
    ) -> None:
        base = build_report(inventory, signals).dependency_level
        if not inventory.dependencies:
            return
        index = data.draw(st.integers(min_value=0, max_value=len(inventory.dependencies) - 1))
        remediate = data.draw(st.sampled_from([_pin, _lock]))
        improved = list(inventory.dependencies)
        if improved[index].ecosystem == "oci":
            return  # oci rows belong to the environment axis
        improved[index] = remediate(improved[index])

        after = build_report(DependencyInventory(dependencies=improved), signals).dependency_level
        assert after >= base

    @given(_INVENTORY, _SIGNALS)
    def test_adding_environment_capture_never_lowers_the_environment_axis(
        self, inventory: DependencyInventory, signals: FileSignals
    ) -> None:
        base = build_report(inventory, signals).environment_level
        for improvement in (
            signals.model_copy(update={"has_dockerfile": True}),
            signals.model_copy(update={"has_nix_file": True}),
        ):
            assert build_report(inventory, improvement).environment_level >= base

    @given(_INVENTORY, _SIGNALS)
    def test_adding_a_vm_never_lowers_the_machine_axis(
        self, inventory: DependencyInventory, signals: FileSignals
    ) -> None:
        base = build_report(inventory, signals).machine_level
        improved = signals.model_copy(update={"has_vm": True})
        assert build_report(inventory, improved).machine_level >= base
