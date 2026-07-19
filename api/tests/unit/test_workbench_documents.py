"""Workbench-derived document routes: scorecard and evaluate report.

Both responses reuse the core producer models as their contract, so the wire
is the models' camelCase dump — these tests pin that the routes validate and
re-serialize a workbench payload without reshaping it into snake_case.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_core.repo_profiler.reproducibility_report import (
    DependencyLevel,
    DependencySummary,
    EnvironmentLevel,
    MachineLevel,
    ReproducibilityReport,
)
from repo2ree_core.reproducibility_scorecard import (
    ReproducibilityScoreCard,
    ScoreCardCategory,
    ScoreCardRung,
)
from repo2ree_supervisor import WorkbenchHandle


def _scorecard() -> ReproducibilityScoreCard:
    rung = ScoreCardRung(key="acquired", label="Source acquired", reached=True)
    return ReproducibilityScoreCard(
        level=1,
        sealed=False,
        categories=[ScoreCardCategory(key="source", label="Source", rungs=[rung])],
    )


def test_scorecard_crosses_as_the_core_models_camelcase_dump(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _scorecard().model_dump(by_alias=True)
    monkeypatch.setattr(workbench_manager, "get_scorecard", lambda handle: payload)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/scorecard")

    assert resp.status_code == 200
    scorecard = resp.json()
    assert scorecard["schemaVersion"] == 1
    assert scorecard["levelCode"] == "R1"
    assert scorecard["levelName"] == "Available"
    assert scorecard["categories"][0]["rungs"][0] == {
        "key": "acquired",
        "label": "Source acquired",
        "reached": True,
        "detail": "",
        "done": None,
        "total": None,
    }


def test_evaluate_report_crosses_as_the_core_models_camelcase_dump(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = ReproducibilityReport(
        dependency_level=DependencyLevel.PINNED,
        environment_level=EnvironmentLevel.CONTAINER,
        machine_level=MachineLevel.NONE,
        dependency_summary=DependencySummary(manifests=1, total=2, pinned=2),
        threats=[],
    )
    artifact = json.dumps(report.model_dump(by_alias=True)).encode()
    monkeypatch.setattr(workbench_manager, "read_artifact_bytes", lambda handle, name: artifact)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/evaluate/report")

    assert resp.status_code == 200
    wire = resp.json()
    assert wire["dependencyLevel"] == int(DependencyLevel.PINNED)
    assert wire["dependencyLevelLabel"] == DependencyLevel.PINNED.label
    assert wire["dependencySummary"]["pinned"] == 2
    assert wire["detectedDependencies"] == "2 dependencies across 1 manifest file"
