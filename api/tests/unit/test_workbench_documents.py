"""Workbench-derived assessment and evaluate-report routes."""

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
from repo2ree_core.domain.ree.model import Ree
from repo2ree_supervisor import WorkbenchHandle


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
    monkeypatch.setattr(workbench_manager, "read_ree_file_bytes", lambda handle, name: artifact)

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
    ree = Ree()
    monkeypatch.setattr(
        workbench_manager,
        "get_ree_state",
        lambda handle: {"ree": ree.model_dump(mode="json")},
    )

    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/receipts/author")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "source": None,
        "evaluation": None,
        "hardware_observation": None,
        "build": None,
        "sbom": None,
        "sbom_cross_check": None,
        "test_activation": None,
        "experiments": {},
    }
