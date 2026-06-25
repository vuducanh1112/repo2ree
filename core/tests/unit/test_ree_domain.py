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
# runtime_entry parsing & defaults
# ================================================


def _entry_for(payload: dict) -> object:
    intent = ReeIntent.model_validate({"name": "x", "runtime_entry": payload})
    return intent.runtime_entry


def test_new_container_entry_round_trips():
    from repo2ree_core.domain.env_entry import ContainerEntry

    entry = _entry_for(
        {
            "kind": "container",
            "engine": "podman",
            "create_args": ["--volume", "/data:/data", "--mac-address", "12:34:56:78:9a:bc"],
        }
    )
    assert isinstance(entry, ContainerEntry)
    assert entry.engine == "podman"
    assert entry.create_args == ["--volume", "/data:/data", "--mac-address", "12:34:56:78:9a:bc"]


def test_default_runtime_entry_is_container_docker():
    from repo2ree_core.domain.env_entry import ContainerEntry

    intent = ReeIntent(name="x")
    assert isinstance(intent.runtime_entry, ContainerEntry)
    assert intent.runtime_entry.engine == "docker"


# ================================================
# Preset + overrides reframe
# ================================================


def test_entry_defaults_to_empty_overrides():
    from repo2ree_core.domain.env_entry import ContainerEntry

    entry = _entry_for({"kind": "container"})
    assert isinstance(entry, ContainerEntry)
    assert entry.overrides.provision == ""
    assert entry.overrides.exec == ""
    assert entry.overrides.teardown == ""
    assert entry.overrides.any_set() is False


def test_legacy_container_entry_without_overrides_still_loads():
    # Manifests written before the reframe carry no `overrides` key.
    from repo2ree_core.domain.env_entry import ContainerEntry

    entry = _entry_for(
        {
            "kind": "container",
            "engine": "podman",
            "env": {"FOO": "bar"},
            "create_args": ["--volume", "/data:/data"],
            "activate": "source .venv/bin/activate",
        }
    )
    assert isinstance(entry, ContainerEntry)
    assert entry.engine == "podman"
    assert entry.activate == "source .venv/bin/activate"
    assert entry.overrides.any_set() is False


def test_container_entry_round_trips_overrides():
    from repo2ree_core.domain.env_entry import ContainerEntry

    entry = _entry_for(
        {
            "kind": "container",
            "overrides": {"exec": "code/run"},
        }
    )
    assert isinstance(entry, ContainerEntry)
    assert entry.overrides.exec == "code/run"
    assert entry.overrides.any_set() is True
    # round-trips through serialization unchanged
    reparsed = _entry_for(entry.model_dump())
    assert reparsed.overrides.exec == "code/run"


def test_custom_entry_still_requires_enter_script():
    from repo2ree_core.domain.env_entry import CustomEntry

    entry = _entry_for({"kind": "custom", "enter_script": "scripts/driver"})
    assert isinstance(entry, CustomEntry)
    assert entry.enter_script == "scripts/driver"

    with pytest.raises(ValidationError, match="enter_script is required"):
        _entry_for({"kind": "custom", "enter_script": ""})
