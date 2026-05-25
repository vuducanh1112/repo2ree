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


def _build_report():
    from repo2ree_core.repo_profiler.reproducibility_report import (
        FileSignals,
        build_report,
    )
    from repo2ree_core.repo_profiler.sources.renovate import parse_renovate_stdout

    renovate_stdout = """
     INFO: Extracted dependencies (repository=local)
    {"pip_requirements":[{"deps":[
      {"depName":"flask","datasource":"pypi"},
      {"depName":"requests","currentValue":"==2.31.0","datasource":"pypi"}
    ],"packageFile":"requirements.txt"}]}
     INFO: Repository finished (repository=local)
    """
    inventory = parse_renovate_stdout(renovate_stdout)
    assert inventory is not None
    return build_report(inventory, FileSignals(has_manifest=True, has_dockerfile=True))


def _wait_for_terminal_run_status(ree_id: str, run_id: str) -> str:
    from repo2ree_api.run_management import _get_run_state

    for _ in range(120):
        status = _get_run_state(ree_id, run_id)["status"]
        if status in {"succeeded", "failed", "canceled"}:
            return status
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} did not reach terminal state in time")


def test_write_report_file_persists_artifact_and_get_endpoint_reads_it():
    from repo2ree_api.evaluate import (
        _report_path,
        _write_report_file,
        get_workspace_evaluate_report,
    )

    ree_id = _make_workspace_with_files()
    report = _build_report()

    _write_report_file(ree_id, report)

    assert _report_path(ree_id).exists()
    on_disk = get_workspace_evaluate_report(ree_id)
    assert "ladderLevel" not in on_disk
    assert on_disk["dependencyLevel"] == 2
    assert on_disk["dependencySummary"]["total"] == 2


def test_get_report_endpoint_404_before_run():
    from fastapi import HTTPException

    from repo2ree_api.evaluate import get_workspace_evaluate_report

    ree_id = _make_workspace_with_files()
    with pytest.raises(HTTPException) as excinfo:
        get_workspace_evaluate_report(ree_id)
    assert excinfo.value.status_code == 404


def test_evaluate_run_succeeds_and_persists_outputs(monkeypatch):
    from repo2ree_api.evaluate import (
        CreateEvaluateRunPayload,
        create_evaluate_run_state,
    )
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_api.storage.workspace_files import get_workspace

    def fake_analyze_repo(repo_path, log=None, strict=False):
        assert repo_path.is_dir()
        assert strict is False
        if log is not None:
            log("system", "error", "Tool exited with code 1")
            log("stdout", "info", "Using extracted dependencies despite config errors")
        return _build_report()

    monkeypatch.setattr("repo2ree_api.evaluate.analyze_repo", fake_analyze_repo)

    ree_id = _make_workspace_with_files()
    run = create_evaluate_run_state(ree_id, CreateEvaluateRunPayload(strict=False))
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(ree_id, run_id) == "succeeded"

    run_state = _get_run_state(ree_id, run_id)
    outputs = run_state["outputs"]
    assert outputs["dependencyCount"] == 2
    assert outputs["manifestCount"] == 1
    assert outputs["dependencyLevel"] == 2
    assert outputs["environmentLevel"] == 1
    assert outputs["machineLevel"] == 0
    assert any(threat["blocking"] for threat in outputs["report"]["threats"])

    detail = get_workspace(ree_id)
    ree_draft = detail["reeDraft"]
    assert ree_draft["dependency_level"] == 2
    assert ree_draft["environment_level"] == 1
    assert ree_draft["machine_level"] == 0
    assert ree_draft["detected_dependencies"] == "2 dependencies across 1 manifest file"

    messages = [entry["message"] for entry in run_state["logs"]]
    assert any("Tool exited with code 1" in msg for msg in messages)
    assert any("Evaluate run succeeded" in msg for msg in messages)


def test_evaluate_run_fails_when_strict_analysis_has_no_extractable_output(monkeypatch):
    from repo2ree_api.evaluate import (
        CreateEvaluateRunPayload,
        create_evaluate_run_state,
    )
    from repo2ree_api.run_management import _get_run_state
    from repo2ree_core.repo_profiler.profiler import AnalysisError

    def fake_analyze_repo(repo_path, log=None, strict=False):
        assert repo_path.is_dir()
        assert strict is True
        raise AnalysisError("Dependency analysis produced no extractable output")

    monkeypatch.setattr("repo2ree_api.evaluate.analyze_repo", fake_analyze_repo)

    ree_id = _make_workspace_with_files()
    run = create_evaluate_run_state(ree_id, CreateEvaluateRunPayload(strict=True))
    run_id = run["runId"]

    assert _wait_for_terminal_run_status(ree_id, run_id) == "failed"

    run_state = _get_run_state(ree_id, run_id)
    assert run_state["outputs"] == {}
    messages = [entry["message"] for entry in run_state["logs"]]
    assert any(
        "Dependency analysis produced no extractable output" in msg for msg in messages
    )
