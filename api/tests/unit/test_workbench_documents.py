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
from repo2ree_core.analysis.repository.reproducibility_report import (
    DependencyLevel,
    DependencySummary,
    EnvironmentLevel,
    MachineLevel,
    ReproducibilityReport,
)
from repo2ree_core.evidence.receipts.consistency import AuthorReceiptEntry, AuthorReceiptSet, ConsistencyStep
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
from repo2ree_core.evidence.scorecard import (
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
    assert scorecard["schema_version"] == 1
    assert scorecard["level_code"] == "R1"
    assert scorecard["level_name"] == "Available"
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
    assert wire["dependency_level"] == int(DependencyLevel.PINNED)
    assert wire["dependency_level_label"] == DependencyLevel.PINNED.label
    assert wire["dependency_summary"]["pinned"] == 2
    assert wire["detected_dependencies"] == "2 dependencies across 1 manifest file"


def test_author_receipts_cross_as_a_typed_document(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = AuthorReceiptSet(
        receipts=[
            AuthorReceiptEntry(
                key="build_runtime",
                receipt=BuildRuntimeReceipt(
                    run_id="build-1",
                    started_at="2026-07-24T00:00:00Z",
                    finished_at="2026-07-24T00:00:01Z",
                    duration_ms=1000,
                    recorded_at="2026-07-24T00:00:01Z",
                    status="succeeded",
                    build_script_path="ree-scripts/build_script.sh",
                    build_script_digest="sha256:abc",
                ),
                consistency=ConsistencyStep(step="build_runtime", status="fresh", run_id="build-1"),
            )
        ]
    )
    monkeypatch.setattr(
        workbench_manager,
        "get_workspace_state",
        lambda handle: {"author_receipts": selected.model_dump()},
    )

    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/receipts/author")

    assert response.status_code == 200
    payload = response.json()
    assert payload["receipts"][0]["receipt"]["operation"] == "build_runtime"
    assert payload["receipts"][0]["consistency"]["status"] == "fresh"
