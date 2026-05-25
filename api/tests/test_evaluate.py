import json

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


_RENOVATE_STDOUT = """
 INFO: Extracted dependencies (repository=local)
{"pip_requirements":[{"deps":[
  {"depName":"flask","datasource":"pypi"},
  {"depName":"requests","currentValue":"==2.31.0","datasource":"pypi"}
],"packageFile":"requirements.txt"}]}
 INFO: Repository finished (repository=local)
"""


def _make_workspace_with_files() -> str:
    from repo2ree_api.storage.workspace_files import (
        WorkspaceCreatePayload,
        create_workspace,
        write_file_content,
    )

    workspace = create_workspace(
        WorkspaceCreatePayload(sourceMode="demo", name="evaluate-test")
    )
    ree_id = workspace["reeId"]
    write_file_content(ree_id, "requirements.txt", "flask\nrequests==2.31.0\n")
    write_file_content(ree_id, "Dockerfile", "FROM python:3.11\n")
    return ree_id


def test_compute_outputs_builds_report_and_writes_artifact():
    from repo2ree_api.evaluate import _compute_evaluate_outputs, _report_path

    ree_id = _make_workspace_with_files()

    outputs = _compute_evaluate_outputs(
        ree_id=ree_id,
        strict=True,
        renovate_stdout=_RENOVATE_STDOUT,
        renovate_exit_code=0,
    )

    # The bare-managers payload shape is normalized by the core analyzer, so the
    # deps are actually seen (the historical API bug is gone).
    assert outputs["dependencyCount"] == 2
    assert outputs["manifestCount"] == 1
    # Pinned deps (no lock) -> dependency axis 2; Dockerfile, no nix -> env 1; no VM -> 0.
    assert outputs["dependencyLevel"] == 2
    assert outputs["environmentLevel"] == 1
    assert outputs["machineLevel"] == 0

    threat_ids = {threat["id"] for threat in outputs["report"]["threats"]}
    assert "unpinned-deps" in threat_ids  # flask
    assert "no-lockfile" in threat_ids  # requests pinned, no lock
    assert "no-nix" in threat_ids  # dockerfile but no nix

    # Standalone artifact file written and readable via the GET endpoint.
    assert _report_path(ree_id).exists()
    on_disk = json.loads(_report_path(ree_id).read_text())
    assert "ladderLevel" not in on_disk
    assert on_disk["dependencyLevel"] == 2
    assert "dependencySummary" in on_disk


def test_get_report_endpoint_404_before_run():
    from fastapi import HTTPException

    from repo2ree_api.evaluate import get_workspace_evaluate_report

    ree_id = _make_workspace_with_files()
    with pytest.raises(HTTPException) as excinfo:
        get_workspace_evaluate_report(ree_id)
    assert excinfo.value.status_code == 404


def test_get_report_endpoint_returns_written_report():
    from repo2ree_api.evaluate import (
        _compute_evaluate_outputs,
        get_workspace_evaluate_report,
    )

    ree_id = _make_workspace_with_files()
    _compute_evaluate_outputs(
        ree_id=ree_id,
        strict=False,
        renovate_stdout=_RENOVATE_STDOUT,
        renovate_exit_code=0,
    )

    report = get_workspace_evaluate_report(ree_id)
    assert report["dependencyLevel"] == 2
    assert any(threat["blocking"] for threat in report["threats"])
