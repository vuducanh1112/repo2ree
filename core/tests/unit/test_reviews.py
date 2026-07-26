from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers import review_acquire_source as handler
from repo2ree_core.reviews import (
    BuildComparison,
    ReviewRecord,
    SourceComparison,
    attempt_basis,
    compare_source_swhids,
    load_reviews,
    new_review_record,
)
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata
from repo2ree_protocol.command import ReviewAcquireSourceArgs


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _author_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, expected_swhid: str | None = None):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git("init", "-q", cwd=origin)
    _git("config", "user.email", "review@example.test", cwd=origin)
    _git("config", "user.name", "Review Test", cwd=origin)
    (origin / "result.txt").write_text("published source\n", encoding="utf-8")
    _git("add", "result.txt", cwd=origin)
    _git("commit", "-qm", "source", cwd=origin)
    revision = _git("rev-parse", "HEAD", cwd=origin)
    swhid = expected_swhid if expected_swhid is not None else directory_swhid(origin)

    ree_root = tmp_path / "ree"
    layout = ReeLayout(root=ree_root)
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree-review",
            name="review",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(
                name="review",
                origin_url=str(origin),
                source_type="git",
                revision=revision,
                swhid=swhid,
            ),
            ree_session=ReeSession(),
        )
    )
    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def test_review_source_acquisition_is_isolated_and_matches_swhid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _author_workspace(tmp_path, monkeypatch)

    result = handler.handle_review_acquire_source(
        ReviewAcquireSourceArgs(review_id="review-one"),
        run_id="review-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "identical"
    assert not any(layout.upstream.iterdir())
    review = layout.review("review-one")
    assert (review.upstream / "result.txt").read_text(encoding="utf-8") == "published source\n"
    assert review.operation_receipt("acquire_source").is_file()
    assert review.comparison("source").is_file()
    records = load_reviews(layout).reviews
    assert len(records) == 1
    assert records[0].source_comparison is not None
    assert records[0].source_comparison.verdict == "identical"


def test_review_source_mismatch_is_a_completed_negative_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _author_workspace(tmp_path, monkeypatch, expected_swhid="swh:1:dir:" + "0" * 40)

    result = handler.handle_review_acquire_source(
        ReviewAcquireSourceArgs(review_id="review-mismatch"),
        run_id="review-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "different"
    record = load_reviews(layout).reviews[0]
    assert record.status == "completed"
    assert record.source_receipt is not None
    assert record.source_comparison is not None
    assert record.source_comparison.verdict == "different"


def test_source_comparison_without_author_swhid_is_inconclusive() -> None:
    comparison = compare_source_swhids("", "swh:1:dir:" + "1" * 40)
    assert comparison.verdict == "inconclusive"


# ================================================
# What an attempt's evidence as a whole is worth
# ================================================


def _attempt_with(
    *,
    source: str | None = None,
    build: str | None = None,
) -> ReviewRecord:
    record = new_review_record("review-basis", at="2026-07-24T10:00:00Z")
    update: dict[str, object] = {}
    if source is not None:
        update["source_comparison"] = SourceComparison(basis=source, verdict="identical")  # type: ignore[arg-type]
    if build is not None:
        update["build_comparison"] = BuildComparison(basis=build, verdict="equivalent")  # type: ignore[arg-type]
    return record.model_copy(update=update)


@pytest.mark.parametrize(
    ("source", "build", "expected"),
    [
        ("independent", "independent", "independent"),
        # One bundled step is enough: nothing downstream of a runtime the REE
        # shipped has been independently reproduced, whatever the source says.
        ("independent", "bundled", "bundled"),
        ("bundled", "independent", "bundled"),
        ("bundled", "bundled", "bundled"),
        # A step that has not settled contributes nothing rather than a default.
        ("independent", None, "independent"),
        (None, "bundled", "bundled"),
    ],
)
def test_an_attempt_is_worth_its_weakest_settled_basis(source: str | None, build: str | None, expected: str) -> None:
    assert attempt_basis(_attempt_with(source=source, build=build)) == expected


def test_an_attempt_that_has_settled_nothing_has_no_basis_to_inherit() -> None:
    """None rather than a default: a step that would have to inherit this has
    no evidence to stand on, and assuming the strong form would invent some."""
    assert attempt_basis(_attempt_with()) is None
