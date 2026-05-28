import time

import pytest


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    from repo2ree_api.settings import service_settings
    from repo2ree_api.storage.init_storage import (
        create_review_storage_if_not_exists,
        create_workspace_storage_if_not_exists,
    )

    monkeypatch.setattr(
        service_settings, "WORKSPACE_STORAGE_DIR", tmp_path / "workspaces"
    )
    monkeypatch.setattr(service_settings, "REVIEWS_STORAGE_DIR", tmp_path / "reviews")
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


def _make_workspace_with_experiment() -> str:
    from repo2ree_api.storage.workspace_files import (
        ReeDraftPatchPayload,
        WorkspaceCreatePayload,
        create_workspace,
        patch_ree_draft,
    )

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="experiment-test")
    )
    ree_id = workspace["reeId"]
    patch_ree_draft(
        ree_id,
        ReeDraftPatchPayload(
            reePatch={
                "runtime": "runtime.tar.gz",
                "experiments": [
                    {
                        "name": "smoke",
                        "command": "echo ok",
                        "outputs": [
                            {
                                "source": {"kind": "stdout"},
                                "match": {"mode": "contains", "value": "ok"},
                            }
                        ],
                    }
                ],
            }
        ),
    )
    from repo2ree_api.storage.workspace_files import workspace_dir

    (workspace_dir(ree_id) / "runtime.tar.gz").write_bytes(b"runtime")
    return ree_id


def test_patch_ree_draft_rejects_stale_expected_version():
    from fastapi.testclient import TestClient

    from repo2ree_api.main import app
    from repo2ree_api.storage.workspace_files import (
        WorkspaceCreatePayload,
        create_workspace,
        read_workspace_metadata,
    )

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="version-conflict-test")
    )
    ree_id = workspace["reeId"]
    original_version = read_workspace_metadata(ree_id)["updatedAt"]

    client = TestClient(app)
    client.patch(
        f"/api/v1/rees/{ree_id}/draft",
        json={"reePatch": {"name": "updated once"}},
    ).raise_for_status()

    response = client.patch(
        f"/api/v1/rees/{ree_id}/draft",
        json={
            "reePatch": {"name": "stale update"},
            "expectedVersion": original_version,
        },
    )
    assert response.status_code == 409


def test_snapshot_run_fails_when_snapshot_persist_conflicts(monkeypatch):
    from repo2ree_core.experiment.experiment import (
        ExpectedOutput,
        Sha256Match,
        StdoutSource,
    )
    from repo2ree_core.experiment.run import ExperimentRunOutcome
    from repo2ree_api.experiment_run import _create_experiment_run_state
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_api.storage.workspace_files import WorkspaceVersionConflictError

    def fake_run_experiment(**kwargs):
        assert kwargs["runtime_archive_path"].name == "runtime.tar.gz"
        return ExperimentRunOutcome(
            status="succeeded",
            run_outputs={
                "experimentName": "smoke",
                "mode": "snapshot",
                "exitCode": 0,
                "snapshotCount": 1,
                "runtimeImage": "repo2ree-runtime-test",
            },
            snapshot_to_persist=[
                ExpectedOutput(
                    source=StdoutSource(kind="stdout"),
                    match=Sha256Match(mode="sha256", value="a" * 64),
                )
            ],
        )

    def fake_persist_snapshot(*args, **kwargs):
        raise WorkspaceVersionConflictError("Workspace version conflict")

    monkeypatch.setattr(
        "repo2ree_api.experiment_run.run_experiment", fake_run_experiment
    )
    monkeypatch.setattr(
        "repo2ree_api.experiment_run._persist_snapshot",
        fake_persist_snapshot,
    )

    ree_id = _make_workspace_with_experiment()
    run = _create_experiment_run_state(ree_id, "smoke", "snapshot")
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(ree_id, run_id) == "failed"

    outputs = _get_run_state(ree_id, run_id)["outputs"]
    assert outputs["snapshotApplied"] is False
    assert "draft changed" in outputs["snapshotMessage"]
