from repo2ree_core.analysis.repository.reproducibility_report import (
    FileSignals,
    Severity,
    ThreatCategory,
    _apt_install_is_unpinned,
    _classify,
    build_report,
)
from repo2ree_core.domain.dependency import Dependency, DependencyInventory

# --------------------------------------------------------------------------- #
# inventory builders
# --------------------------------------------------------------------------- #


def _dep(
    name: str,
    constraint: str | None = None,
    *,
    manifest: str = "requirements.txt",
    locked: str | None = None,
) -> Dependency:
    return Dependency(
        ecosystem="pypi",
        name=name,
        declared_constraint=constraint,
        declared_in=manifest,
        locked_version=locked,
        locked_in="uv.lock" if locked else None,
    )


def _image(name: str, tag: str | None, digest: str | None = None) -> Dependency:
    return Dependency(
        ecosystem="oci",
        name=name,
        declared_constraint=tag,
        declared_in="Dockerfile",
        locked_hashes=[digest] if digest else [],
    )


def _mixed_inventory() -> DependencyInventory:
    """One unpinned, two pinned, two ranged deps across two manifests, plus a
    floating base image."""
    return DependencyInventory(
        dependencies=[
            _dep("flask"),
            _dep("requests", "==2.31.0"),
            _dep("numpy", ">=1.20"),
            _dep("pandas", "==2.1.0", manifest="pyproject.toml"),
            _dep("rich", ">=13", manifest="pyproject.toml"),
            _image("python", "3.11"),
        ]
    )


def _pinned_no_lock_inventory() -> DependencyInventory:
    return DependencyInventory(
        dependencies=[
            _dep("requests", "==2.31.0"),
            _dep("pandas", "==2.1.0"),
        ]
    )


def _locked_inventory() -> DependencyInventory:
    return DependencyInventory(
        dependencies=[
            _dep("requests", ">=2", locked="2.31.0"),
            _dep("numpy", ">=1.20", locked="1.26.4"),
        ]
    )


def _threat_ids(report) -> set[str]:
    return {threat.id for threat in report.threats}


def _blocking_ids(report) -> set[str]:
    return {threat.id for threat in report.threats if threat.blocking}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def test_classify_buckets():
    assert _classify("==2.1.0") == "pinned"
    assert _classify("2.1.0") == "pinned"
    assert _classify(">=1.20") == "ranged"
    assert _classify("^1.2") == "ranged"
    assert _classify(None) == "unpinned"
    assert _classify("") == "unpinned"
    # conda (`=1.21.0`) and npm (`=1.2.3`) spell exact pins with one `=`.
    assert _classify("=1.21.0") == "pinned"
    # Wildcard components float, however pin-shaped the rest looks.
    assert _classify("1.x") == "ranged"
    assert _classify("2.7.X") == "ranged"
    assert _classify("==1.*") == "ranged"
    assert _classify("=>1.0") == "ranged"


def test_apt_heuristic():
    assert _apt_install_is_unpinned("RUN apt-get install -y curl") is True
    assert _apt_install_is_unpinned("RUN apt-get install -y curl=7.88.1-10") is False
    assert _apt_install_is_unpinned("RUN echo hello") is False


# --------------------------------------------------------------------------- #
# build_report
# --------------------------------------------------------------------------- #


def test_mixed_sample_threats_and_summary():
    report = build_report(_mixed_inventory(), FileSignals(has_dockerfile=True))
    summary = report.dependency_summary
    assert (summary.total, summary.pinned, summary.ranged, summary.unpinned) == (
        5,
        2,
        2,
        1,
    )
    assert summary.locked == 0
    assert summary.manifests == 2  # requirements.txt + pyproject.toml, not Dockerfile

    ids = _threat_ids(report)
    assert {"unpinned-deps", "range-pins", "no-lockfile", "floating-base-image"} <= ids
    # container present (dockerfile, no nix) -> no-nix; not no-container
    assert "no-nix" in ids
    assert "no-container" not in ids

    unpinned = next(t for t in report.threats if t.id == "unpinned-deps")
    assert any("flask" in entry for entry in unpinned.affected)
    assert unpinned.category is ThreatCategory.DEPENDENCY
    assert unpinned.severity is Severity.HIGH


def test_report_rows_carry_the_summary_classification():
    """Every dependency row ships the same status the summary bucketed it
    into — one classifier, observable per row on the wire."""
    from collections import Counter

    report = build_report(_mixed_inventory(), FileSignals(has_dockerfile=True))
    library = [d for d in report.dependencies if d.ecosystem != "oci" and d.direct]
    counts = Counter(d.status for d in library)
    summary = report.dependency_summary
    assert counts.get("pinned", 0) == summary.pinned
    assert counts.get("ranged", 0) == summary.ranged
    assert counts.get("unpinned", 0) == summary.unpinned
    assert counts.get("locked", 0) == summary.locked
    serialized = report.model_dump(by_alias=True)
    assert all("status" in row for row in serialized["dependencies"])


def test_mixed_sample_axes_are_independent():
    report = build_report(_mixed_inventory(), FileSignals(has_dockerfile=True))
    # Dependency axis: exact pins but no lockfile -> Pinned (2).
    assert report.dependency_level == 2
    # Environment axis: a container, but not declarative -> Container (1).
    assert report.environment_level == 1
    # Machine axis: no VM image -> None (0).
    assert report.machine_level == 0

    # Each axis gates one blocking threat, independently.
    assert _blocking_ids(report) == {"no-lockfile", "no-nix", "no-vm"}
    assert report.threats[0].blocking is True
    # the floating base image is still reported, just not the gate
    assert "floating-base-image" in _threat_ids(report)


def test_pinned_no_lock_pins_deps_but_has_no_environment():
    report = build_report(_pinned_no_lock_inventory(), FileSignals())
    assert report.dependency_level == 2  # Pinned
    assert report.environment_level == 0  # None
    assert report.machine_level == 0  # None
    assert _threat_ids(report) == {"no-lockfile", "no-container", "no-vm"}
    # one blocking threat per axis
    assert _blocking_ids(report) == {"no-lockfile", "no-container", "no-vm"}


def test_locked_deps_reach_locked_axis_but_no_environment():
    report = build_report(_locked_inventory(), FileSignals())
    s = report.dependency_summary
    assert (s.total, s.locked) == (2, 2)
    assert report.dependency_level == 3  # Locked
    assert report.environment_level == 0  # None
    # A locked dependency axis raises no dependency threats; only env + machine do.
    assert _threat_ids(report) == {"no-container", "no-vm"}


def test_partially_locked_deps_do_not_reach_locked_axis():
    inventory = DependencyInventory(
        dependencies=[
            _dep("locked", locked="1.0.0"),
            _dep("floating", ">=2.0"),
        ]
    )

    report = build_report(inventory, FileSignals())

    assert report.dependency_level == 2
    assert "range-pins" in _threat_ids(report)
    assert "no-lockfile" not in _threat_ids(report)


def test_transitive_closure_rows_do_not_count():
    """direct=False lock rows (the lockfile's transitive closure) stay out of
    the summary and the threat lists."""
    inventory = DependencyInventory(
        dependencies=[
            _dep("requests", ">=2", locked="2.31.0"),
            Dependency(
                ecosystem="pypi",
                name="urllib3",
                direct=False,
                locked_version="2.2.1",
                locked_in="uv.lock",
            ),
        ]
    )
    report = build_report(inventory, FileSignals())
    assert report.dependency_summary.total == 1
    assert report.dependency_level == 3  # Locked — the closure row is not a gap


def test_manifest_signal_without_parsed_deps_scores_declared():
    report = build_report(None, FileSignals(has_manifest=True))

    assert report.dependency_level == 1
    assert report.dependency_summary.manifests == 1
    assert "no-manifest" not in _threat_ids(report)


def test_vm_present_satisfies_machine_axis():
    report = build_report(
        _locked_inventory(),
        FileSignals(has_nix_file=True, has_vm=True),
    )
    # Locked deps, declarative env, and a VM -> the ideal, no threats at all.
    assert report.dependency_level == 3
    assert report.environment_level == 2  # Declarative
    assert report.machine_level == 1  # VM
    assert _threat_ids(report) == set()


def test_empty_inventory_yields_no_manifest_and_no_environment():
    report = build_report(DependencyInventory(), FileSignals())
    assert (
        report.dependency_level,
        report.environment_level,
        report.machine_level,
    ) == (
        0,
        0,
        0,
    )
    assert _threat_ids(report) == {"no-manifest", "no-container", "no-vm"}
    assert report.dependency_summary.total == 0


def test_pinned_base_image_is_not_floating():
    inventory = DependencyInventory(dependencies=[_image("python", "3.11", digest="sha256:abc")])
    report = build_report(inventory, FileSignals(has_manifest=True, has_dockerfile=True))
    assert "floating-base-image" not in _threat_ids(report)


def test_unpinned_apt_detected_from_dockerfile_text():
    report = build_report(
        _pinned_no_lock_inventory(),
        FileSignals(
            has_manifest=True,
            has_dockerfile=True,
            dockerfile_texts=["FROM python:3.11\nRUN apt-get install -y curl"],
        ),
    )
    assert "unpinned-apt" in _threat_ids(report)


def test_report_serializes_camel_case():
    report = build_report(_pinned_no_lock_inventory(), FileSignals())
    dumped = report.model_dump(by_alias=True)
    assert {"dependency_level", "environment_level", "machine_level"} <= set(dumped)
    assert "ladderLevel" not in dumped
    assert {
        "dependency_level_label",
        "environment_level_label",
        "machine_level_label",
    } <= set(dumped)
    assert "dependency_summary" in dumped
    assert set(dumped["dependency_summary"]).issuperset(
        {"manifests", "total", "pinned", "ranged", "unpinned", "locked"}
    )
