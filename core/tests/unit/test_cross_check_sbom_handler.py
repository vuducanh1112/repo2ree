"""Unit coverage for the cross_check_sbom envelope handler.

The handler joins two persisted artifacts — the workspace SBOM and the
reproducibility report — enriches the report in place, and records the
aggregate receipt. These tests point ``ReeLayout.in_workbench`` at a tmp root
and seed both artifacts directly; the pure merge has its own suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers import cross_check_sbom as handler
from repo2ree_core.receipts import CrossCheckSbomReceipt, load_receipts
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata
from repo2ree_protocol.command import CrossCheckSbomArgs
from repo2ree_protocol.result import ActionResult


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


_REPORT = {
    "dependencyLevel": 3,
    "environmentLevel": 1,
    "machineLevel": 0,
    "dependencySummary": {"manifests": 1, "total": 1, "locked": 1},
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
            reeId="ree123",
            name="demo",
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-01T00:00:00Z",
            reeIntent=ReeIntent(name="demo", sbom="sbom.json"),
            reeSession=ReeSession(source_available=True),
        )
    )
    if with_sbom:
        (layout.workspace / "sbom.json").write_text(json.dumps(_SBOM), encoding="utf-8")
    if with_report:
        layout.artifacts.mkdir(parents=True, exist_ok=True)
        (layout.artifacts / "reproducibility-report.json").write_text(json.dumps(_REPORT), encoding="utf-8")
    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return layout


def _run() -> ActionResult:
    return handler.handle_cross_check_sbom(
        CrossCheckSbomArgs(), run_id="run-1", log=_silent_log, is_canceled=_never_canceled
    )


def test_canceled_before_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    result = handler.handle_cross_check_sbom(
        CrossCheckSbomArgs(), run_id="run-1", log=_silent_log, is_canceled=lambda: True
    )
    assert result.status == "canceled"


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
    (layout.artifacts / "reproducibility-report.json").write_text("not json", encoding="utf-8")
    result = _run()
    assert result.status == "failed"
    (receipt,) = load_receipts(layout)
    assert isinstance(receipt, CrossCheckSbomReceipt)
    assert receipt.status == "failed"


def test_enriches_report_and_records_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch)
    result = _run()
    assert result.status == "succeeded"

    persisted = json.loads((layout.artifacts / "reproducibility-report.json").read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in persisted["dependencies"]}
    assert rows["requests"]["runtime_presence"] == "observed"
    assert rows["requests"]["observed_version"] == "2.31.0"
    assert rows["certifi"]["status"] == "undeclared"
    summary = persisted["sbomCrossCheck"]
    assert summary["declaredDirectTotal"] == 1
    assert summary["observedMatched"] == 1
    assert summary["undeclaredSameEcosystem"] == 1
    assert summary["sbomDigest"]
    assert summary["checkedAt"]

    (receipt,) = load_receipts(layout)
    assert isinstance(receipt, CrossCheckSbomReceipt)
    assert receipt.status == "succeeded"
    assert receipt.sbom_digest == summary["sbomDigest"]
    assert receipt.observed_matched == 1
    assert receipt.observed_total == 2


def test_rerun_does_not_double_count_undeclared_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch)
    assert _run().status == "succeeded"
    assert _run().status == "succeeded"
    persisted = json.loads((layout.artifacts / "reproducibility-report.json").read_text(encoding="utf-8"))
    undeclared = [row for row in persisted["dependencies"] if row["status"] == "undeclared"]
    assert len(undeclared) == 1
