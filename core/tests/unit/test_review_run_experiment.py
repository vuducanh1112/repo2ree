"""Reviewer-side experiments: what settles a result, and what refuses to.

The load-bearing choice this step makes is that the *author's verify script* is
the criterion, not the output bytes. Most of what is pinned here is the shape of
that choice: a result that differs byte for byte but passes verify is a
reproduction, a result verify rejects is a verdict rather than a broken step,
and the two ways of having no criterion at all are inconclusive rather than
free passes.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.digests import Digest, digest_bytes, digest_file_if_exists
from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.domain.primitives import RunId, ScriptPath, WorkspacePath
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import BuildRuntimeReceipt, RunExperimentReceipt
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.review.models import (
    ActivationOutcome,
    ActivationVerdict,
    BuildComparison,
    EvidenceBasis,
    ReviewRecord,
    SourceComparison,
    experiment_comparison,
    new_review_record,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import load_reviews, write_review_record
from repo2ree_core.operations.handlers.review import run_experiment as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.metadata import WorkspaceMetadata
from repo2ree_core.persistence.receipts import record_receipt
from repo2ree_core.reserved_paths import experiment_slug
from repo2ree_core.time_utils import parse_utc_instant
from repo2ree_protocol.command import ReviewRunExperimentArgs

RUNTIME_PATH = "runtime.tar"
REVIEW_ID = "review-one"
EXPERIMENT = "headline-result"

_RUN_SCRIPT = "ree-scripts/experiments/headline-result.sh"
_VERIFY_SCRIPT = "ree-scripts/experiments/headline-result.verify.sh"
_OUTPUT = "results/out.csv"

# Writes a result whose bytes differ on every run — the ordinary case for
# anything that records a time, a seed, or a hostname.
_RUN_WRITES_VARYING_OUTPUT = f'#!/bin/sh\nset -eu\nmkdir -p results\necho "value=42 at $(date +%s%N)" > {_OUTPUT}\n'
_RUN_WRITES_FIXED_OUTPUT = f'#!/bin/sh\nset -eu\nmkdir -p results\necho "value=42" > {_OUTPUT}\n'
_RUN_FAILS = "#!/bin/sh\nexit 9\n"
# The author's criterion: the value is what matters, not the bytes around it.
_VERIFY_ACCEPTS = f"#!/bin/sh\nset -eu\ngrep -q 'value=42' {_OUTPUT}\n"
_VERIFY_REJECTS = "#!/bin/sh\nexit 3\n"


def _experiment(*, verify: bool = True, outputs: bool = True) -> Experiment:
    return Experiment(
        name=EXPERIMENT,
        run_script=_RUN_SCRIPT,
        verify_script=_VERIFY_SCRIPT if verify else "",
        output_paths=[_OUTPUT] if outputs else [],
    )


def _author_ree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    experiment: Experiment | None = None,
) -> ReeLayout:
    layout = ReeLayout(root=tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree-review",
            name="review",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(
                name="review",
                runtime=RUNTIME_PATH,
                experiments=[experiment or _experiment()],
            ),
            ree_state=ReeLifecycleState(),
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def _author_ran_it(
    layout: ReeLayout,
    *,
    verify_exit_code: int | None = 0,
    verify_script_digest: str | None = digest_bytes(_VERIFY_ACCEPTS.encode()),
    output_digest: str | None = None,
) -> None:
    """Record the author's own run of the experiment — the baseline to reproduce."""
    record_receipt(
        layout,
        RunExperimentReceipt(
            run_id=RunId("author-experiment"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:01Z"),
            duration_ms=1000,
            recorded_at=parse_utc_instant("2026-01-01T00:00:01Z"),
            status="succeeded",
            experiment_name=EXPERIMENT,
            run_script_path=ScriptPath(_RUN_SCRIPT),
            verify_script_path=ScriptPath(_VERIFY_SCRIPT),
            verify_script_digest=Digest(verify_script_digest) if verify_script_digest else None,
            verify_exit_code=verify_exit_code,
            produced_output_digest=Digest(output_digest) if output_digest else None,
        ),
        log=lambda *_: None,
    )


def _inhabitable_attempt(
    layout: ReeLayout,
    *,
    run_script: str | None = _RUN_WRITES_VARYING_OUTPUT,
    verify_script: str | None = _VERIFY_ACCEPTS,
    activation_verdict: ActivationVerdict = "passed",
    source_basis: EvidenceBasis = "independent",
    build_basis: EvidenceBasis = "independent",
    certified_digest: str | None = None,
) -> ReviewLayout:
    """An attempt through activation: a workspace, a certified runtime, a pass.

    Assembled by hand rather than by driving the three earlier handlers, so each
    test can disturb exactly one thing the experiments step depends on.
    """
    review = layout.review(REVIEW_ID)
    review.workspace.mkdir(parents=True, exist_ok=True)
    runtime = review.workspace / RUNTIME_PATH
    runtime.write_text("runtime bytes\n", encoding="utf-8")

    for path, body in ((_RUN_SCRIPT, run_script), (_VERIFY_SCRIPT, verify_script)):
        if body is None:
            continue
        script = review.workspace / path
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(body, encoding="utf-8")

    record = new_review_record(REVIEW_ID, at="2026-07-24T10:00:00Z")
    for step, at in (("source", "10:00:01"), ("build", "10:00:02"), ("activation", "10:00:03")):
        record = with_step(record, step, status="completed", at=f"2026-07-24T{at}Z")  # type: ignore[arg-type]
    record = record.model_copy(
        update={
            "source_comparison": SourceComparison(basis=source_basis, verdict="identical"),
            "build_comparison": BuildComparison(basis=build_basis, verdict="equivalent"),
            "build_receipt": BuildRuntimeReceipt(
                run_id=RunId("review-build"),
                started_at=parse_utc_instant("2026-07-24T10:00:01Z"),
                finished_at=parse_utc_instant("2026-07-24T10:00:02Z"),
                duration_ms=1000,
                recorded_at=parse_utc_instant("2026-07-24T10:00:02Z"),
                status="succeeded",
                runtime_path=WorkspacePath(RUNTIME_PATH),
                produced_runtime_digest=(
                    Digest(certified_digest) if certified_digest is not None else digest_file_if_exists(runtime)
                ),
            ),
            "activation_outcome": ActivationOutcome(
                basis=build_basis,
                verdict=activation_verdict,
                runtime_digest=digest_file_if_exists(runtime),
            ),
        }
    )
    write_review_record(review, record)
    return review


def _reproduce(experiment_name: str = EXPERIMENT, review_id: str = REVIEW_ID) -> Any:
    return handler.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=review_id, experiment_name=experiment_name),
        run_id="review-experiment-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )


def _record(layout: ReeLayout) -> ReviewRecord:
    return load_reviews(layout).reviews[0]


# ================================================
# What settles a result
# ================================================


def test_a_result_the_authors_verify_script_accepts_is_reproduced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of the whole design: differing output bytes, passing criterion.

    The run writes a timestamp into its output, so the digests cannot match. The
    author's own verify script accepts it anyway — which is exactly what the
    author said correctness means, so it reproduced.
    """
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout, output_digest="sha256:something-else")
    _inhabitable_attempt(layout)

    result = _reproduce()

    assert result.status == "succeeded"
    comparison = result.outputs["comparison"]
    assert comparison["verdict"] == "reproduced"
    assert comparison["policy"] == "verify-script"
    assert comparison["expected_output_digest"] != comparison["observed_output_digest"]


def test_matching_output_bytes_earn_the_stronger_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    review = _inhabitable_attempt(layout, run_script=_RUN_WRITES_FIXED_OUTPUT)
    # Run once to learn what the deterministic output digests to, then hand that
    # to the author's baseline so both sides agree byte for byte.
    _reproduce()
    observed = experiment_comparison(_record(layout), EXPERIMENT)
    assert observed is not None
    _author_ran_it(layout, output_digest=observed.observed_output_digest)
    write_review_record(review, _record(layout).model_copy(update={"experiment_comparisons": []}))

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "identical"


def test_a_rejected_result_is_a_verdict_not_a_broken_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reviewer's machine did its job and found the most valuable thing it
    can. Recording it as a step failure would report the review as broken."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout, verify_script_digest=digest_bytes(_VERIFY_REJECTS.encode()))
    _inhabitable_attempt(layout, verify_script=_VERIFY_REJECTS)

    result = _reproduce()

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "different"
    record = _record(layout)
    assert step_state(record, "experiments").status == "completed"  # type: ignore[union-attr]
    assert record.status == "completed"
    assert record.failure is None


def test_a_run_that_never_produced_a_result_is_different_rather_than_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify never ran because the run script died. That is a failure to
    reproduce the result, not an absence of criterion."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    _inhabitable_attempt(layout, run_script=_RUN_FAILS)

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "different"
    assert result.outputs["comparison"]["run_exit_code"] == 9


# ================================================
# Absent criteria are never passes
# ================================================


def test_an_experiment_with_no_verify_script_is_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a verify script the only fact left is "the run script exited 0",
    which for a script whose last act is writing a file says nothing about the
    result. A free verdict would certify nothing."""
    layout = _author_ree(tmp_path, monkeypatch, experiment=_experiment(verify=False))
    _author_ran_it(layout)
    _inhabitable_attempt(layout, verify_script=None)

    result = _reproduce()

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "inconclusive"


def test_an_older_author_receipt_still_carries_its_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``verify_exit_code`` post-dates the receipt schema, and REEs authored
    before it record the verdict only in ``status`` — which the runner sets to
    succeeded exactly when verify passed. Reading only the literal field would
    report a missing schema field as a missing scientific claim, making every
    older REE inconclusive on its most important step."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout, verify_exit_code=None)
    _inhabitable_attempt(layout)

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "reproduced"
    assert result.outputs["comparison"]["expected_verify_exit_code"] == 0


def test_an_experiment_the_author_never_ran_is_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No baseline claim exists to have reproduced — the same rule the build
    step applies to a missing author SBOM."""
    layout = _author_ree(tmp_path, monkeypatch)
    _inhabitable_attempt(layout)

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "inconclusive"


def test_an_author_receipt_without_a_bound_criterion_is_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout, verify_script_digest=None)
    _inhabitable_attempt(layout)

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "inconclusive"
    assert result.outputs["comparison"]["expected_verify_script_digest"] is None


def test_a_changed_verify_script_cannot_certify_the_authors_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    review = _inhabitable_attempt(layout, verify_script="#!/bin/sh\nexit 0\n")

    result = _reproduce()

    comparison = result.outputs["comparison"]
    assert comparison["verdict"] == "inconclusive"
    assert comparison["expected_verify_script_digest"] != comparison["verify_script_digest"]
    assert comparison["verify_script_digest"] == digest_file_if_exists(review.workspace / _VERIFY_SCRIPT)


def test_the_verdict_names_the_criterion_it_rests_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A "reproduced" is worth exactly as much as the script that granted it, so
    the script it ran is recorded rather than summarised away."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    review = _inhabitable_attempt(layout)

    result = _reproduce()

    comparison = result.outputs["comparison"]
    assert comparison["verify_script_path"] == _VERIFY_SCRIPT
    assert comparison["expected_verify_script_digest"] == digest_bytes(_VERIFY_ACCEPTS.encode())
    assert comparison["verify_script_digest"] == digest_file_if_exists(review.workspace / _VERIFY_SCRIPT)
    assert result.outputs["receipt"]["verify_script_digest"] == comparison["verify_script_digest"]


# ================================================
# Preconditions
# ================================================


def test_experiments_refuse_a_runtime_that_would_not_come_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every experiment would fail for one reason that has nothing to do with
    the experiments, and a wall of "different" would bury it."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    _inhabitable_attempt(layout, activation_verdict="failed")

    result = _reproduce()

    assert result.status == "failed"
    assert "would not come up" in (result.failure.message if result.failure else "")
    assert step_state(_record(layout), "experiments").status == "failed"  # type: ignore[union-attr]


def test_experiments_refuse_an_attempt_that_never_activated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    review = layout.review(REVIEW_ID)
    review.workspace.mkdir(parents=True, exist_ok=True)
    write_review_record(review, new_review_record(REVIEW_ID, at="2026-07-24T10:00:00Z"))

    result = _reproduce()

    assert result.status == "failed"
    assert step_state(_record(layout), "experiments").status == "failed"  # type: ignore[union-attr]


def test_a_stale_runtime_stops_the_step_rather_than_judging_a_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The build was re-run since activation, so a result produced now would be
    attached to a runtime that no longer exists."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    _inhabitable_attempt(layout, certified_digest="sha256:a-runtime-that-is-gone")

    result = _reproduce()

    assert result.status == "failed"
    assert "re-run the build review" in (result.failure.message if result.failure else "")


def test_an_unknown_experiment_name_fails_the_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _inhabitable_attempt(layout)

    result = _reproduce(experiment_name="not-an-experiment")

    assert result.status == "failed"
    assert step_state(_record(layout), "experiments").status == "failed"  # type: ignore[union-attr]


def test_a_reclaimed_workspace_says_how_to_get_it_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    review = _inhabitable_attempt(layout)
    shutil.rmtree(review.workspace)

    result = _reproduce()

    assert result.status == "failed"
    assert "re-run the build review" in (result.failure.message if result.failure else "")


# ================================================
# Evidence, kept per experiment
# ================================================


def test_each_experiment_keeps_its_own_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two experiments share one operation name, so a per-operation receipt slot
    would leave the attempt holding one experiment's evidence for both."""
    second = Experiment(name="second", run_script=_RUN_SCRIPT, verify_script=_VERIFY_SCRIPT)
    layout = _author_ree(tmp_path, monkeypatch)
    layout_store = ReeDirectory(layout)
    metadata = layout_store.read_metadata()
    intent = metadata.ree_intent.model_copy(update={"experiments": [_experiment(), second]})
    layout_store.write_metadata(metadata.model_copy(update={"ree_intent": intent}))
    _author_ran_it(layout)
    review = _inhabitable_attempt(layout)

    _reproduce()
    _reproduce(experiment_name="second")

    record = _record(layout)
    assert {entry.experiment_name for entry in record.experiment_comparisons} == {EXPERIMENT, "second"}
    assert {entry.experiment_name for entry in record.experiment_receipts} == {EXPERIMENT, "second"}
    for name in (EXPERIMENT, "second"):
        assert review.experiment_receipt(experiment_slug(name)).is_file()
        assert review.experiment_comparison(experiment_slug(name)).is_file()


def test_re_running_one_experiment_leaves_its_siblings_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    second = Experiment(name="second", run_script=_RUN_SCRIPT, verify_script=_VERIFY_SCRIPT)
    layout = _author_ree(tmp_path, monkeypatch)
    store = ReeDirectory(layout)
    metadata = store.read_metadata()
    store.write_metadata(
        metadata.model_copy(
            update={"ree_intent": metadata.ree_intent.model_copy(update={"experiments": [_experiment(), second]})}
        )
    )
    _author_ran_it(layout)
    _inhabitable_attempt(layout)

    _reproduce(experiment_name="second")
    _reproduce()
    _reproduce()

    record = _record(layout)
    assert len(record.experiment_comparisons) == 2
    assert experiment_comparison(record, "second") is not None


def test_a_bundled_attempt_reproduces_a_result_without_claiming_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The verdict is the same; what it is worth is carried by the basis, which
    the step inherits rather than chooses."""
    layout = _author_ree(tmp_path, monkeypatch)
    _author_ran_it(layout)
    _inhabitable_attempt(layout, build_basis="bundled")

    result = _reproduce()

    assert result.outputs["comparison"]["verdict"] == "reproduced"
    assert result.outputs["comparison"]["basis"] == "bundled"
