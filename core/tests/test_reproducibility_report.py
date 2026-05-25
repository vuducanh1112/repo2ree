import json
from pathlib import Path

from repo2ree_core.repo_profiler.reproducibility_report import (
    FileSignals,
    Severity,
    ThreatCategory,
    _apt_install_is_unpinned,
    _classify,
    _package_files,
    build_report,
)

FIXTURES = Path(__file__).parent / "fixtures" / "renovate"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _threat_ids(report) -> set[str]:
    return {threat.id for threat in report.threats}


def _blocking(report):
    blocking = [threat for threat in report.threats if threat.blocking]
    return blocking[0] if blocking else None


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


def test_package_files_accepts_both_shapes():
    bare = {"pip_requirements": [{"deps": []}]}
    wrapped = {"packageFiles": bare}
    assert _package_files(bare) == bare
    assert _package_files(wrapped) == bare
    assert _package_files(None) == {}


def test_apt_heuristic():
    assert _apt_install_is_unpinned("RUN apt-get install -y curl") is True
    assert _apt_install_is_unpinned("RUN apt-get install -y curl=7.88.1-10") is False
    assert _apt_install_is_unpinned("RUN echo hello") is False


# --------------------------------------------------------------------------- #
# build_report over fixtures
# --------------------------------------------------------------------------- #


def test_mixed_sample_threats_and_summary():
    report = build_report(
        _load("mixed_sample.json"),
        FileSignals(has_dockerfile=True),
    )
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
    # container present (dockerfile, no nix) -> no-nix; not no-container (nothing locked)
    assert "no-nix" in ids
    assert "no-container" not in ids

    unpinned = next(t for t in report.threats if t.id == "unpinned-deps")
    assert any("flask" in entry for entry in unpinned.affected)
    assert unpinned.category is ThreatCategory.DEPENDENCY
    assert unpinned.severity is Severity.HIGH


def _blocking_ids(report) -> set[str]:
    return {threat.id for threat in report.threats if threat.blocking}


def test_mixed_sample_axes_are_independent():
    report = build_report(
        _load("mixed_sample.json"),
        FileSignals(has_dockerfile=True),
    )
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
    report = build_report(
        _load("pinned_no_lock.json"),
        FileSignals(),
    )
    assert report.dependency_level == 2  # Pinned
    assert report.environment_level == 0  # None
    assert report.machine_level == 0  # None
    assert _threat_ids(report) == {"no-lockfile", "no-container", "no-vm"}
    # one blocking threat per axis
    assert _blocking_ids(report) == {"no-lockfile", "no-container", "no-vm"}


def test_locked_deps_reach_locked_axis_but_no_environment():
    report = build_report(
        _load("locked_uv.json"),
        FileSignals(),
    )
    s = report.dependency_summary
    assert (s.total, s.locked) == (2, 2)
    assert report.dependency_level == 3  # Locked
    assert report.environment_level == 0  # None
    # A locked dependency axis raises no dependency threats; only env + machine do.
    assert _threat_ids(report) == {"no-container", "no-vm"}


def test_partially_locked_deps_do_not_reach_locked_axis():
    payload = {
        "pip_requirements": [
            {
                "packageFile": "requirements.txt",
                "deps": [
                    {
                        "depName": "locked",
                        "datasource": "pypi",
                        "lockedVersion": "1.0.0",
                    },
                    {
                        "depName": "floating",
                        "datasource": "pypi",
                        "currentValue": ">=2.0",
                    },
                ],
            }
        ]
    }

    report = build_report(payload, FileSignals())

    assert report.dependency_level == 2
    assert "range-pins" in _threat_ids(report)
    assert "no-lockfile" not in _threat_ids(report)


def test_manifest_signal_without_renovate_deps_scores_declared():
    report = build_report(None, FileSignals(has_manifest=True))

    assert report.dependency_level == 1
    assert report.dependency_summary.manifests == 1
    assert "no-manifest" not in _threat_ids(report)


def test_vm_present_satisfies_machine_axis():
    report = build_report(
        _load("locked_uv.json"),
        FileSignals(has_nix_file=True, has_vm=True),
    )
    # Locked deps, declarative env, and a VM -> the ideal, no threats at all.
    assert report.dependency_level == 3
    assert report.environment_level == 2  # Declarative
    assert report.machine_level == 1  # VM
    assert _threat_ids(report) == set()


def test_empty_payload_yields_no_manifest_and_no_environment():
    report = build_report(_load("empty.json"), FileSignals())
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


def test_unpinned_apt_detected_from_dockerfile_text():
    report = build_report(
        _load("pinned_no_lock.json"),
        FileSignals(
            has_manifest=True,
            has_dockerfile=True,
            dockerfile_texts=["FROM python:3.11\nRUN apt-get install -y curl"],
        ),
    )
    assert "unpinned-apt" in _threat_ids(report)


def test_report_serializes_camel_case():
    report = build_report(_load("pinned_no_lock.json"), FileSignals())
    dumped = report.model_dump(by_alias=True)
    assert {"dependencyLevel", "environmentLevel", "machineLevel"} <= set(dumped)
    assert "ladderLevel" not in dumped
    assert {
        "dependencyLevelLabel",
        "environmentLevelLabel",
        "machineLevelLabel",
    } <= set(dumped)
    assert "dependencySummary" in dumped
    assert set(dumped["dependencySummary"]).issuperset(
        {"manifests", "total", "pinned", "ranged", "unpinned", "locked"}
    )
