"""Unit coverage for the generate_sbom handler's staging and cancellation.

The scanner writes its own output file, so the handler scans into a staging
sibling and promotes it only once syft has finished cleanly — ``artifacts/sbom.json``
is the path the intent points at, and a partial document there would leave the
REE declaring an SBOM that no longer parses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_core.analysis.sbom.scan import ScanOutcome
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.operations.handlers.author import generate_sbom as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.persistence.receipts import load_receipts
from repo2ree_core.persistence.record import ReeRecord
from repo2ree_protocol.command import GenerateSbomArgs
from repo2ree_protocol.result import ActionResult

_RUNTIME = "runtime-image.tar"
_PRIOR_SBOM = {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [{"name": "prior"}]}
_NEW_SBOM = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "components": [{"name": "requests", "purl": "pkg:pypi/requests@2.31.0"}],
    "metadata": {"tools": {"components": [{"name": "syft", "version": "1.2.3"}]}},
}


def _silent_log(*_: object) -> None:
    return None


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_prior_sbom: bool = False) -> ReeLayout:
    layout = ReeLayout(root=tmp_path)
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_record(
        ReeRecord(
            ree_id="ree123",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(name="demo"),
            ree_state=ReeLifecycleState(source_available=True),
        )
    )
    store.workspace.write_bytes(_RUNTIME, b"not really a tarball")
    if with_prior_sbom:
        layout.artifacts.mkdir(parents=True, exist_ok=True)
        layout.sbom.write_text(json.dumps(_PRIOR_SBOM), encoding="utf-8")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return layout


def _stub_scan(monkeypatch: pytest.MonkeyPatch, outcome: ScanOutcome, *, writes: bool = True) -> None:
    """Stand in for syft, which writes its output file itself — partial or not."""

    def scan(_runtime: Path, output_path: Path, **_kwargs: object) -> ScanOutcome:
        if writes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(_NEW_SBOM), encoding="utf-8")
        return outcome

    monkeypatch.setattr(handler, "scan_runtime_archive", scan)


def _run() -> ActionResult:
    return handler.handle_generate_sbom(
        GenerateSbomArgs(produced_runtime_path=_RUNTIME),
        run_id="run-1",
        log=_silent_log,
        is_canceled=lambda: False,
    )


def test_a_successful_scan_publishes_the_document_and_declares_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _seed(tmp_path, monkeypatch)
    _stub_scan(monkeypatch, ScanOutcome(returncode=0, tool_version="1.2.3"))

    result = _run()

    assert result.status == "succeeded"
    assert json.loads(layout.sbom.read_text(encoding="utf-8")) == _NEW_SBOM
    assert ReeDirectory(layout).read_intent().sbom == SBOM_ARTIFACT_PATH


def test_a_canceled_scan_leaves_the_previous_sbom_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cancel mid-scan must not publish the partial document syft left."""
    layout = _seed(tmp_path, monkeypatch, with_prior_sbom=True)
    _stub_scan(monkeypatch, ScanOutcome(returncode=-15, canceled=True))

    result = _run()

    assert result.status == "canceled"
    assert json.loads(layout.sbom.read_text(encoding="utf-8")) == _PRIOR_SBOM


def test_a_failed_scan_leaves_the_previous_sbom_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _seed(tmp_path, monkeypatch, with_prior_sbom=True)
    _stub_scan(monkeypatch, ScanOutcome(returncode=2))

    result = _run()

    assert result.status == "failed"
    assert result.exit_code == 2
    assert json.loads(layout.sbom.read_text(encoding="utf-8")) == _PRIOR_SBOM


def test_a_scan_that_did_not_finish_leaves_no_staging_file_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _seed(tmp_path, monkeypatch, with_prior_sbom=True)
    _stub_scan(monkeypatch, ScanOutcome(returncode=2))

    _run()

    assert sorted(p.name for p in layout.artifacts.iterdir()) == ["sbom.json"]


def test_a_canceled_scan_records_a_canceled_receipt_declaring_no_sbom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The receipt is the record of what happened, including that it stopped."""
    layout = _seed(tmp_path, monkeypatch)
    _stub_scan(monkeypatch, ScanOutcome(returncode=-15, canceled=True))

    _run()

    receipts = load_receipts(layout)
    assert [r.status for r in receipts] == ["canceled"]
    assert receipts[0].sbom_path is None  # type: ignore[union-attr]


def test_a_canceled_scan_does_not_declare_an_sbom_on_the_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _seed(tmp_path, monkeypatch)
    _stub_scan(monkeypatch, ScanOutcome(returncode=-15, canceled=True))

    _run()

    assert ReeDirectory(layout).read_intent().sbom is None
