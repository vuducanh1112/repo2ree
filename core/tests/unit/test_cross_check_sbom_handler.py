"""Unit coverage for the cross_check_sbom operations handler.

The handler joins two persisted artifacts — the REE's SBOM and its
reproducibility report, both in ``artifacts/`` — enriches the report in place,
and records the aggregate receipt. These tests point ``ReeLayout.in_workbench`` at a tmp root
and seed both artifacts directly; the pure merge has its own suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.evidence.receipts.models import CrossCheckSbomReceipt
from repo2ree_core.evidence.receipts.store import load_receipts
from repo2ree_core.operations.handlers.author import cross_check_sbom as handler
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata
from repo2ree_protocol.result import ActionResult


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


_REPORT = {
    "dependency_level": 3,
    "environment_level": 1,
    "machine_level": 0,
    "dependency_summary": {"manifests": 1, "total": 1, "locked": 1},
    "dependencies": [
        {
            "ecosystem": "pypi",
            "name": "requests",
            "declared_constraint": "==2.31.0",
            "declared_in": "requirements.txt",
            "locked_version": "2.31.0",
            "status": "locked",
        }
    ],
    "threats": [],
}

_SBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "components": [
        {"name": "requests", "purl": "pkg:pypi/requests@2.31.0"},
        {"name": "certifi", "purl": "pkg:pypi/certifi@2024.2.2"},
    ],
}


def _seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_sbom: bool = True,
    with_report: bool = True,
) -> ReeLayout:
    layout = ReeLayout(root=tmp_path)
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree123",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(name="demo", sbom=SBOM_ARTIFACT_PATH),
            ree_session=ReeSession(source_available=True),
        )
    )
    layout.artifacts.mkdir(parents=True, exist_ok=True)
    if with_sbom:
        layout.sbom.write_text(json.dumps(_SBOM), encoding="utf-8")
    if with_report:
        layout.reproducibility_report.write_text(json.dumps(_REPORT), encoding="utf-8")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return layout


def _run() -> ActionResult:
    return handler.handle_cross_check_sbom(run_id="run-1", log=_silent_log, is_canceled=_never_canceled)


def test_missing_sbom_fails_without_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch, with_sbom=False)
    result = _run()
    assert result.status == "failed"
    assert load_receipts(layout) == []


def test_missing_report_fails_without_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch, with_report=False)
    result = _run()
    assert result.status == "failed"
    assert load_receipts(layout) == []


def test_unreadable_report_records_failed_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch)
    layout.reproducibility_report.write_text("not json", encoding="utf-8")
    result = _run()
    assert result.status == "failed"
    (receipt,) = load_receipts(layout)
    assert isinstance(receipt, CrossCheckSbomReceipt)
    assert receipt.status == "failed"


def test_enriches_report_and_records_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch)
    result = _run()
    assert result.status == "succeeded"

    persisted = json.loads(layout.reproducibility_report.read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in persisted["dependencies"]}
    assert rows["requests"]["runtime_presence"] == "observed"
    assert rows["requests"]["observed_version"] == "2.31.0"
    assert rows["certifi"]["status"] == "undeclared"
    summary = persisted["sbom_cross_check"]
    assert summary["declared_direct_total"] == 1
    assert summary["observed_matched"] == 1
    assert summary["undeclared_same_ecosystem"] == 1
    assert summary["sbom_digest"]
    assert summary["checked_at"]

    (receipt,) = load_receipts(layout)
    assert isinstance(receipt, CrossCheckSbomReceipt)
    assert receipt.status == "succeeded"
    assert receipt.sbom_digest == summary["sbom_digest"]
    assert receipt.observed_matched == 1
    assert receipt.observed_total == 2


def test_rerun_does_not_double_count_undeclared_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch)
    assert _run().status == "succeeded"
    assert _run().status == "succeeded"
    persisted = json.loads(layout.reproducibility_report.read_text(encoding="utf-8"))
    undeclared = [row for row in persisted["dependencies"] if row["status"] == "undeclared"]
    assert len(undeclared) == 1
