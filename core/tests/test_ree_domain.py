import pytest
from pydantic import ValidationError
from repo2ree_core.domain.ree_intent import ReeIntent


# ================================================
# Helpers
# ================================================


def _intent_with_experiments(*names: str) -> ReeIntent:
    return ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [{"name": n, "command": "pytest"} for n in names],
        }
    )


# ================================================
# Experiment name uniqueness
# ================================================


def test_unique_experiment_names_accepts_distinct_names():
    intent = _intent_with_experiments("smoke", "integration", "benchmark")
    assert [e.name for e in intent.experiments] == ["smoke", "integration", "benchmark"]


def test_unique_experiment_names_rejects_duplicates():
    with pytest.raises(ValidationError, match="experiment names must be unique"):
        _intent_with_experiments("smoke", "integration", "smoke")


def test_unique_experiment_names_allows_multiple_empty_names():
    intent = _intent_with_experiments("", "", "smoke")
    assert len(intent.experiments) == 3


def test_unique_experiment_names_allows_empty_list():
    intent = ReeIntent(name="demo")
    assert intent.experiments == []


def test_experiment_estimates_default_to_empty_strings():
    intent = ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [{"name": "smoke", "command": "pytest -q"}],
        }
    )

    experiment = intent.experiments[0]
    assert experiment.runtime_estimate == ""
    assert experiment.resource_estimates.model_dump() == {
        "cpu": "",
        "memory": "",
        "gpu": "",
        "storage": "",
        "network": "",
    }


def test_experiment_estimates_accept_runtime_and_resource_hints():
    intent = ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [
                {
                    "name": "benchmark",
                    "command": "python bench.py",
                    "runtime_estimate": "15-20 min",
                    "resource_estimates": {
                        "cpu": "8 vCPU",
                        "memory": "16 GB",
                        "gpu": "1x A10",
                        "storage": "5 GB scratch",
                        "network": "offline",
                    },
                }
            ],
        }
    )

    experiment = intent.experiments[0]
    assert experiment.runtime_estimate == "15-20 min"
    assert experiment.resource_estimates.model_dump() == {
        "cpu": "8 vCPU",
        "memory": "16 GB",
        "gpu": "1x A10",
        "storage": "5 GB scratch",
        "network": "offline",
    }


# ================================================
# PackagingPolicy
# ================================================


def test_packaging_defaults_to_excluded():
    intent = ReeIntent(name="demo")
    assert intent.packaging.source_included is False
    assert intent.packaging.runtime_included is False


def test_packaging_survives_apply_patch():
    intent = ReeIntent(name="demo")
    patched = intent.apply_patch(
        {"packaging": {"source_included": True, "runtime_included": False}}
    )
    assert patched.packaging.source_included is True
    assert patched.packaging.runtime_included is False


def test_packaging_appears_in_manifest():
    intent = ReeIntent.model_validate(
        {
            "name": "demo",
            "packaging": {"source_included": True, "runtime_included": True},
        }
    )
    manifest = intent.as_manifest()
    assert manifest["source_included"] is True
    assert manifest["runtime_included"] is True


# ================================================
# ReeSession transitions
# ================================================


def test_session_with_source_sets_available():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_source(
        {
            "mode": "download",
            "snapshotArchive": "snapshot.tar.gz",
            "completedAt": "2026-01-01T00:00:00Z",
        }
    )
    assert updated.source_available is True
    assert updated.source_acquired_by == "download"
    assert updated.source_snapshot_archive == "snapshot.tar.gz"


def test_session_with_source_none_clears_fields():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession(source_available=True, source_acquired_by="download")
    cleared = session.with_source(None)
    assert cleared.source_available is False
    assert cleared.source_acquired_by == ""


def test_session_with_evaluation():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_evaluation(
        dependency_level=3, environment_level=2, machine_level=0
    )
    assert updated.dependency_level == 3
    assert updated.environment_level == 2
    assert updated.machine_level == 0


def test_session_has_no_apply_patch():
    from repo2ree_core.domain.ree_session import ReeSession

    assert not hasattr(ReeSession, "apply_patch")
