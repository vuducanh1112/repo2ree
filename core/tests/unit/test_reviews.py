from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_core.domain.primitives import RunId
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import RunExperimentReceipt
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.review.comparison import compare_experiment_results, compare_source_swhids
from repo2ree_core.evidence.review.models import (
    BuildComparison,
    ExperimentComparison,
    ReviewRecord,
    SourceComparison,
    attempt_basis,
    experiment_comparison,
    new_review_record,
    with_experiment,
)
from repo2ree_core.evidence.review.store import load_reviews
from repo2ree_core.operations.handlers.review import acquire_source as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.record import ReeRecord
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import parse_utc_instant
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
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_record(
        ReeRecord(
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
            ree_state=ReeLifecycleState(),
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
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


# ================================================
# What settles an experiment's result
# ================================================


def _compare_experiment(**overrides: object) -> ExperimentComparison:
    kwargs: dict[str, object] = {
        "experiment_name": "headline",
        "basis": "independent",
        "verify_script_path": "ree-scripts/experiments/headline.verify.sh",
        "expected_verify_script_digest": "sha256:criterion",
        "verify_script_digest": "sha256:criterion",
        "expected_verify_exit_code": 0,
        "observed_verify_exit_code": 0,
        "run_exit_code": 0,
    }
    kwargs.update(overrides)
    return compare_experiment_results(**kwargs)  # type: ignore[arg-type]


def test_a_passing_verify_script_reproduces_a_result_whatever_the_bytes_say() -> None:
    """The whole point of judging by criterion rather than by output: a run that
    stamps a timestamp differs byte for byte on every honest reproduction."""
    comparison = _compare_experiment(
        expected_output_digest="sha256:author-bytes",
        observed_output_digest="sha256:reviewer-bytes",
    )

    assert comparison.verdict == "reproduced"


def test_matching_outputs_earn_the_stronger_verdict() -> None:
    comparison = _compare_experiment(
        expected_output_digest="sha256:same",
        observed_output_digest="sha256:same",
    )

    assert comparison.verdict == "identical"


def test_a_rejected_result_is_different() -> None:
    assert _compare_experiment(observed_verify_exit_code=1).verdict == "different"


def test_a_run_whose_verify_never_ran_is_different_rather_than_inconclusive() -> None:
    """The run died before its results could be judged. That is a failure to
    reproduce, not an absence of criterion."""
    comparison = _compare_experiment(observed_verify_exit_code=None, run_exit_code=9)

    assert comparison.verdict == "different"


def test_an_experiment_with_no_criterion_is_never_a_pass() -> None:
    """Without a verify script the only remaining fact is that the run script
    exited 0, which says nothing about the result it wrote."""
    comparison = _compare_experiment(verify_script_path="", verify_script_digest=None)

    assert comparison.verdict == "inconclusive"


def test_an_absent_author_baseline_is_not_agreement() -> None:
    """The same rule the build step applies to a missing author SBOM."""
    comparison = _compare_experiment(expected_verify_exit_code=None)

    assert comparison.verdict == "inconclusive"


def test_an_unbound_author_criterion_is_not_agreement() -> None:
    comparison = _compare_experiment(expected_verify_script_digest=None)

    assert comparison.verdict == "inconclusive"


def test_a_changed_criterion_cannot_reproduce_the_original_claim() -> None:
    comparison = _compare_experiment(verify_script_digest="sha256:changed")

    assert comparison.verdict == "inconclusive"


def test_an_author_whose_own_verify_failed_left_no_accepted_claim() -> None:
    """A selected nonzero receipt is malformed evidence, not a baseline that a
    reviewer can turn into an accepted result by running the criterion again."""
    comparison = _compare_experiment(expected_verify_exit_code=1, observed_verify_exit_code=1)

    assert comparison.verdict == "inconclusive"


# ================================================
# Per-experiment evidence on the record
# ================================================


def _experiment_receipt(name: str) -> RunExperimentReceipt:
    return RunExperimentReceipt(
        run_id=RunId(f"run-{name}"),
        started_at=parse_utc_instant("2026-07-24T10:00:00Z"),
        finished_at=parse_utc_instant("2026-07-24T10:00:01Z"),
        duration_ms=1000,
        recorded_at=parse_utc_instant("2026-07-24T10:00:01Z"),
        status="succeeded",
        experiment_name=name,
    )


def test_experiments_are_keyed_by_name_so_a_re_run_replaces_only_itself() -> None:
    record = new_review_record("review-exp", at="2026-07-24T10:00:00Z")
    record = with_experiment(record, _experiment_receipt("a"), _compare_experiment(experiment_name="a"))
    record = with_experiment(record, _experiment_receipt("b"), _compare_experiment(experiment_name="b"))
    record = with_experiment(
        record,
        _experiment_receipt("a"),
        _compare_experiment(experiment_name="a", observed_verify_exit_code=1),
    )

    assert [entry.experiment_name for entry in record.experiment_comparisons] == ["a", "b"]
    assert experiment_comparison(record, "a").verdict == "different"  # type: ignore[union-attr]
    assert experiment_comparison(record, "b").verdict == "reproduced"  # type: ignore[union-attr]


def test_an_experiment_that_never_ran_has_no_comparison() -> None:
    record = new_review_record("review-exp", at="2026-07-24T10:00:00Z")

    assert experiment_comparison(record, "never-run") is None
