from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ree_definitions import SNAPSHOT_DIGEST, ree_definition, write_snapshot

from repo2ree_core.analysis.repository.profiler import analyze_repo
from repo2ree_core.domain.ree.transitions import commit_receipt
from repo2ree_core.operations.handlers.author import acquire_source, evaluate_reproducibility
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import AcquireSourceArgs, EvaluateReproducibilityArgs
from repo2ree_ree.model import Ree, ReeSubject, SourceDefinition
from repo2ree_ree.primitives import RunId, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.reproducibility import ReproducibilityReport

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def _acquired(tmp_path: Path) -> ReeLayout:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    source = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")
    receipt = AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url=source.origin_url,
        source_type="git",
        resolved_revision="abc123",
        snapshot_digest=SNAPSHOT_DIGEST,
    )
    store.write_ree(commit_receipt(Ree(subject=ReeSubject(definition=ree_definition(source=source))), receipt))
    write_snapshot(layout)
    return layout


def test_a_current_evaluation_answers_from_its_report_and_a_stricter_one_evaluates_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _acquired(tmp_path)
    analyzed: list[bool] = []

    def counted(path: Path, **kwargs: Any) -> ReproducibilityReport:
        analyzed.append(bool(kwargs.get("strict")))
        return analyze_repo(path, **kwargs)

    monkeypatch.setattr(evaluate_reproducibility, "analyze_repo", counted)

    def evaluate(run_id: str, **args: bool) -> str:
        return evaluate_reproducibility.handle_evaluate_reproducibility(
            EvaluateReproducibilityArgs(**args),
            layout=layout,
            run_id=run_id,
            log=lambda *a: None,
            is_canceled=lambda: False,
        ).status

    assert evaluate("evaluate-1") == "succeeded"
    assert evaluate("evaluate-2") == "succeeded"
    assert analyzed == [False]
    assert evaluate("evaluate-3", strict=True) == "failed"
    assert evaluate("evaluate-4", again=True) == "succeeded"
    assert analyzed == [False, True, False]


def test_the_same_download_asked_for_again_fetches_nothing_and_another_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _acquired(tmp_path)

    def fetches(*args: object, **kwargs: object) -> None:
        raise AssertionError("nothing is fetched for a source acquired already")

    monkeypatch.setattr(acquire_source, "_perform", fetches)

    def acquire(origin_url: str) -> str:
        return acquire_source.handle_acquire_source(
            AcquireSourceArgs(mode="download", origin_url=origin_url, source_type="git"),
            layout=layout,
            run_id="acquire-again",
            log=lambda *a: None,
            is_canceled=lambda: False,
        ).status

    assert acquire("https://example.test/repo.git") == "succeeded"
    assert acquire("https://example.test/another.git") == "failed"
