import time

import pytest


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    from repo2ree_api.settings import service_settings
    from repo2ree_api.storage.init_storage import (
        create_review_storage_if_not_exists,
        create_workspace_storage_if_not_exists,
    )

    workspace_dir = tmp_path / "workspaces"
    reviews_dir = tmp_path / "reviews"
    monkeypatch.setattr(service_settings, "WORKSPACE_STORAGE_DIR", workspace_dir)
    monkeypatch.setattr(service_settings, "REVIEWS_STORAGE_DIR", reviews_dir)
    create_workspace_storage_if_not_exists()
    create_review_storage_if_not_exists()

    yield tmp_path


def _wait_for_terminal_run_status(ree_id: str, run_id: str) -> str:
    from repo2ree_api.run_management import _get_run_state

    for _ in range(120):
        status = _get_run_state(ree_id, run_id)["status"]
        if status in {"succeeded", "failed", "canceled"}:
            return status
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} did not reach terminal state in time")


def test_hbom_run_profiles_machine_and_persists_hardware_description(monkeypatch):
    from repo2ree_core.domain.hbom import HBOM
    from repo2ree_api.generate_hbom import (
        CreateGenerateHbomRunPayload,
        create_generate_hbom_run_state,
    )
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_api.storage.workspace_files import (
        WorkspaceCreatePayload,
        create_workspace,
        get_workspace,
    )

    def fake_generate_hbom():
        return HBOM.model_validate(
            {
                "cpus": {
                    "AMD EPYC 9004": {
                        "vendor": "AMD",
                        "quantity": 2,
                        "cores_per_cpu": 64,
                        "threads_per_core": 2,
                        "architecture": "x86_64",
                        "extra_info": {"logical_cpus": 256},
                    }
                },
                "gpus": {},
                "memory": {
                    "Installed Memory": {
                        "vendor": "",
                        "quantity": 1,
                        "capacity_gb": 512.0,
                        "memory_type": "DDR5",
                        "speed_mt_s": 0,
                        "extra_info": {"aggregate": True},
                    }
                },
                "storage": {},
                "network": {},
                "extra_info": {"profiled_on": "test-host"},
            }
        )

    monkeypatch.setattr("repo2ree_api.generate_hbom.generate_hbom", fake_generate_hbom)

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="hbom-success-test")
    )
    workspace_id = workspace["reeId"]

    run = create_generate_hbom_run_state(
        workspace_id,
        CreateGenerateHbomRunPayload(),
    )
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(workspace_id, run_id) == "succeeded"

    outputs = _get_run_state(workspace_id, run_id)["outputs"]
    assert outputs["componentCounts"]["cpus"] == 1
    assert outputs["componentCounts"]["memory"] == 1
    assert outputs["hardwareDescription"]["cpus"]["AMD EPYC 9004"]["quantity"] == 2

    detail = get_workspace(workspace_id)
    ree_draft = detail.get("reeDraft") or {}
    hardware = ree_draft.get("hardware_description") or {}
    assert hardware["cpus"]["AMD EPYC 9004"]["cores_per_cpu"] == 64
    assert hardware["memory"]["Installed Memory"]["capacity_gb"] == 512.0

    messages = [
        entry["message"] for entry in _get_run_state(workspace_id, run_id)["logs"]
    ]
    assert any("Starting hbom run" in msg for msg in messages)
    assert any("Generated hardware description" in msg for msg in messages)


def test_hbom_run_marks_failed_when_generation_errors(monkeypatch):
    from repo2ree_api.generate_hbom import (
        CreateGenerateHbomRunPayload,
        create_generate_hbom_run_state,
    )
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_api.storage.workspace_files import (
        WorkspaceCreatePayload,
        create_workspace,
    )

    def fake_generate_hbom():
        raise RuntimeError("host profiling failed")

    monkeypatch.setattr("repo2ree_api.generate_hbom.generate_hbom", fake_generate_hbom)

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="hbom-failure-test")
    )
    workspace_id = workspace["reeId"]

    run = create_generate_hbom_run_state(
        workspace_id,
        CreateGenerateHbomRunPayload(),
    )
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(workspace_id, run_id) == "failed"

    messages = [
        entry["message"] for entry in _get_run_state(workspace_id, run_id)["logs"]
    ]
    assert any(
        "HBOM generation failed: host profiling failed" in msg for msg in messages
    )


def test_hbom_run_preserves_manual_entries_when_profile_machine_runs(monkeypatch):
    from repo2ree_core.domain.hbom import HBOM
    from repo2ree_api.generate_hbom import (
        CreateGenerateHbomRunPayload,
        create_generate_hbom_run_state,
    )
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_api.storage.workspace_files import (
        WorkspaceCreatePayload,
        WorkspacePatchPayload,
        create_workspace,
        get_workspace,
        patch_workspace,
    )

    def fake_generate_hbom():
        return HBOM.model_validate(
            {
                "cpus": {
                    "Detected CPU": {
                        "vendor": "AMD",
                        "quantity": 1,
                        "cores_per_cpu": 32,
                        "threads_per_core": 2,
                        "architecture": "x86_64",
                        "extra_info": {},
                    }
                },
                "gpus": {},
                "memory": {},
                "storage": {},
                "network": {},
                "extra_info": {"profiled_on": "test-host"},
            }
        )

    monkeypatch.setattr("repo2ree_api.generate_hbom.generate_hbom", fake_generate_hbom)

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="hbom-merge-test")
    )
    workspace_id = workspace["reeId"]
    patch_workspace(
        workspace_id,
        WorkspacePatchPayload(
            reePatch={
                "hardware_description": {
                    "cpus": {
                        "Manual CPU": {
                            "vendor": "Intel",
                            "quantity": 1,
                            "cores_per_cpu": 8,
                            "threads_per_core": 2,
                            "architecture": "x86_64",
                            "extra_info": {"source": "manual"},
                        }
                    },
                    "memory": {
                        "Manual RAM": {
                            "vendor": "Samsung",
                            "quantity": 4,
                            "capacity_gb": 32.0,
                            "memory_type": "DDR5",
                            "speed_mt_s": 5600,
                            "extra_info": {"source": "manual"},
                        }
                    },
                }
            }
        ),
    )

    run = create_generate_hbom_run_state(
        workspace_id,
        CreateGenerateHbomRunPayload(),
    )
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(workspace_id, run_id) == "succeeded"

    outputs = _get_run_state(workspace_id, run_id)["outputs"]["hardwareDescription"]
    assert "Manual CPU" in outputs["cpus"]
    assert "Detected CPU" in outputs["cpus"]
    assert "Manual RAM" in outputs["memory"]

    detail = get_workspace(workspace_id)
    hardware = (detail.get("reeDraft") or {}).get("hardware_description") or {}
    assert "Manual CPU" in hardware["cpus"]
    assert "Detected CPU" in hardware["cpus"]
    assert hardware["memory"]["Manual RAM"]["vendor"] == "Samsung"


def test_ree_from_metadata_normalizes_legacy_invalid_hardware_description_payload():
    from repo2ree_core.domain.ree import REE

    ree = REE.from_metadata(
        {
            "reeDraft": {
                "name": "legacy-hbom",
                "hardware_description": {
                    "memory": "asdasd",
                    "cpu": "awdasd",
                    "gpu": "awdwad",
                },
            }
        }
    )

    assert ree.hardware_description.memory == {}
    assert ree.hardware_description.cpus == {}
    assert ree.hardware_description.gpus == {}
    assert ree.hardware_description.extra_info == {
        "memory": "asdasd",
        "cpu": "awdasd",
        "gpu": "awdwad",
    }
