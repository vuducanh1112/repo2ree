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
            "experiments": [{"name": n, "run_script": "ree/exp.sh"} for n in names],
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
            "experiments": [{"name": "smoke", "run_script": "ree/exp.sh"}],
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
                    "run_script": "ree/bench.sh",
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
# ReeSession transitions
# ================================================


def test_session_with_source_sets_available():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_source(
        acquired_by="download",
        snapshot_archive="snapshot.tar.gz",
        snapshot_captured_at="2026-01-01T00:00:00Z",
    )
    assert updated.source_available is True
    assert updated.source_acquired_by == "download"
    assert updated.source_snapshot_archive == "snapshot.tar.gz"


def test_session_with_source_records_resolved_commit():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_source(
        acquired_by="download",
        resolved_commit="abc123",
    )
    assert updated.source_resolved_commit == "abc123"


def test_session_with_evaluation():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_evaluation(
        dependency_level=3,
        environment_level=2,
        machine_level=0,
        detected_dependencies="4 dependencies across 1 manifest file",
    )
    assert updated.dependency_level == 3
    assert updated.environment_level == 2
    assert updated.machine_level == 0
    assert updated.detected_dependencies == "4 dependencies across 1 manifest file"


def test_session_with_packaging():
    from repo2ree_core.domain.ree_session import ReeSession

    session = ReeSession()
    updated = session.with_packaging(source_included=True, runtime_included=True)
    assert updated.source_included is True
    assert updated.runtime_included is True
    assert session.source_included is False


def test_session_has_no_apply_patch():
    from repo2ree_core.domain.ree_session import ReeSession

    assert not hasattr(ReeSession, "apply_patch")
    assert not hasattr(ReeSession, "with_downloadables")


# ================================================
# run-script defaults and validation
# ================================================


def test_default_activation_run_script_is_reserved():
    intent = ReeIntent(name="x")
    assert intent.activation.run_script == "ree/activation.sh"


def test_experiment_run_script_round_trips():
    intent = ReeIntent.model_validate(
        {
            "name": "x",
            "experiments": [{"name": "smoke", "run_script": "ree/experiments/smoke.sh"}],
        }
    )
    assert intent.experiments[0].run_script == "ree/experiments/smoke.sh"


@pytest.mark.parametrize("path", ["/setup.sh", "../setup.sh", "scripts/../setup.sh"])
def test_run_script_rejects_unsafe_paths(path):
    with pytest.raises(ValidationError):
        ReeIntent.model_validate(
            {
                "name": "x",
                "experiments": [{"name": "smoke", "run_script": path}],
            }
        )
