"""Workbench-derived audit and evaluate-report routes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from ree_definitions import bare_ree

from repo2ree_api.deps import command_dispatcher
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_ree.reproducibility import (
    DependencyLevel,
    DependencySummary,
    EnvironmentLevel,
    MachineLevel,
    ReproducibilityReport,
)
from repo2ree_supervisor import ReeRoute


def test_evaluate_report_crosses_as_the_core_models_camelcase_dump(
    client: TestClient,
    online_ree: ReeRoute,
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
    monkeypatch.setattr(command_dispatcher, "read_ree_file_bytes", lambda handle, name: artifact)

    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}/reproducibility-report")

    assert resp.status_code == 200
    wire = resp.json()
    assert wire["dependency_level"] == int(DependencyLevel.PINNED)
    assert wire["dependency_level_label"] == DependencyLevel.PINNED.label
    assert wire["dependency_summary"]["pinned"] == 2
    assert wire["detected_dependencies"] == "2 dependencies across 1 manifest file"


def test_author_receipts_cross_as_a_typed_document(
    client: TestClient,
    online_ree: ReeRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ree = bare_ree()
    monkeypatch.setattr(
        command_dispatcher,
        "get_ree_state",
        lambda handle: WorkbenchReeDocument(
            ree=ree, status="draft", audit=audit(ree), steps=ree_steps(ree, audit(ree))
        ),
    )

    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/receipts/author")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "acquire_source": None,
        "evaluate_reproducibility": None,
        "observe_hardware": None,
        "check_working_environment": None,
        "build_experiment_environment": None,
        "generate_sbom": None,
        "cross_check_sbom": None,
        "activate_experiment_environment": None,
        "experiments": {},
    }
