"""Reproduce one of the author's experiments inside a review attempt.

The last step of the reviewer lifecycle, and the one the other three exist to
make possible: source establishes that the code is the author's, build that the
environment is theirs, activation that it comes up — and this asks the question
a reader actually came with, which is whether the result holds.

What settles it is the author's own verify script. Output bytes are the wrong
bar and deliberately not the verdict: a run that stamps a timestamp, draws a
seed, or records a hostname writes different bytes on every honest
reproduction, so demanding equality would report failure for results that
reproduced perfectly, and would do it most often for exactly the
computationally interesting experiments. The author already declared what
counts as a correct result when they wrote the verify script, so this step
re-runs that declaration against the reviewer's own results and reports what it
said. Matching output digests are recorded as a stronger tier where they
happen, never as a requirement (see
:func:`repo2ree_core.evidence.review.comparison.compare_experiment_results`).

The cost of that choice is that a verdict is worth exactly as much as the
script that granted it, and verify scripts range from a tolerance check against
reference values to ``test -f results.csv``. Two things keep that honest rather
than hidden: an experiment declaring no verify script at all is ``inconclusive``
rather than a free pass, and the comparison records the verify script's digest
so a reader can see which criterion they are trusting.

Activation must have *passed*, not merely completed, before this runs. Every
experiment inside a runtime that would not come up fails for one reason that
has nothing to do with the experiments, and recording a wall of ``different``
verdicts would bury the single fact that explains them all.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file_if_exists, digest_output_paths
from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.evidence.receipts.models import RunExperimentReceipt, experiment_step_key, receipt_envelope
from repo2ree_core.evidence.receipts.store import load_author_receipts
from repo2ree_core.evidence.review.comparison import compare_experiment_results
from repo2ree_core.evidence.review.models import (
    EvidenceBasis,
    ExperimentComparison,
    with_experiment,
    with_step,
)
from repo2ree_core.evidence.review.store import write_review_experiment_evidence, write_review_record
from repo2ree_core.execution.experiment.resolve import RunnableResolutionError, resolve_experiment_runnable
from repo2ree_core.execution.experiment.run import run_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.review import (
    begin_review_step,
    require_certified_runtime,
    require_completed_step,
    require_review_record,
)
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import ReviewRunExperimentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewRunExperimentOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    experiment_name: str
    receipt: RunExperimentReceipt
    comparison: ExperimentComparison


def handle_review_run_experiment(
    args: ReviewRunExperimentArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(args.review_id)
    timer = OperationTimer.start()

    record = require_review_record(review_layout, args.review_id, log)
    if isinstance(record, ActionResult):
        return record

    started, stop = begin_review_step(
        review_layout,
        record,
        "experiments",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review experiment",
    )

    if is_canceled():
        return stop("canceled", "canceled before the experiment")

    halted = require_completed_step(
        started,
        "activation",
        stop=stop,
        message="Probe the runtime before reproducing results in it",
    )
    if halted is not None:
        return halted

    # Completed is not enough: activation completes with a `failed` verdict when
    # the runtime would not come up, and every experiment run inside such a
    # runtime would report a result failure that is really the activation
    # failure wearing a different hat.
    if started.activation_outcome is None or started.activation_outcome.verdict != "passed":
        return stop("failed", "This attempt's runtime would not come up; its results cannot be reproduced in it")

    certified = require_certified_runtime(
        started,
        review_layout,
        stop=stop,
        purpose="to run experiments in",
        retry_purpose="to reproduce results",
    )
    if isinstance(certified, ActionResult):
        return certified

    try:
        experiment = resolve_experiment_runnable(ReeStore(ree_layout).read_intent(), args.experiment_name)
    except RunnableResolutionError as exc:
        return stop("failed", f"the author baseline cannot run this experiment: {exc}")

    if not (review_layout.workspace / experiment.run_script).is_file():
        return stop(
            "failed",
            f"the author baseline declares a run script that is not there: {experiment.run_script}",
        )

    outcome = run_runnable(
        workspace=review_layout.workspace.resolve(),
        runnable=experiment,
        label=experiment.name,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled" or is_canceled():
        return stop("canceled", "the experiment was canceled")

    comparison = _certify(
        ree_layout,
        experiment=experiment,
        basis=certified.basis,
        run_exit_code=outcome.run_outputs.exit_code,
        observed_verify_exit_code=outcome.run_outputs.verify_exit_code,
        observed_output_digest=digest_output_paths(review_layout.workspace, experiment.output_paths),
        runtime_digest=certified.runtime_digest,
        # The criterion as it stood in the workspace it ran in, not as the author
        # recorded it: this digest is what lets a reader audit which script
        # granted the verdict they are being asked to trust.
        verify_script_digest=(
            digest_file_if_exists(review_layout.workspace / experiment.verify_script)
            if experiment.verify_script
            else None
        ),
    )

    timing = timer.finish()
    receipt = RunExperimentReceipt(
        **receipt_envelope(run_id, timing, outcome.status),
        experiment_name=experiment.name,
        run_script_path=experiment.run_script,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_script_path=experiment.verify_script,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
        runtime_path=certified.runtime_path or None,
        declared_runtime_digest=certified.runtime_digest,
        produced_output_digest=comparison.observed_output_digest,
    )
    write_review_experiment_evidence(review_layout, receipt, comparison)
    write_review_record(
        review_layout,
        with_step(
            with_experiment(started, receipt, comparison),
            "experiments",
            # Completed whatever the verdict: an experiment whose results do not
            # reproduce is this step doing its job, and the finding is the most
            # valuable thing a review produces. Only the conditions that stop it
            # running at all are step failures.
            status="completed",
            at=timing.finished_at,
        ),
    )
    _log_verdict(comparison, log=log)
    log(
        "system",
        "info",
        f"review experiment completed in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )

    outputs = ReviewRunExperimentOutputs(
        review_id=args.review_id,
        experiment_name=experiment.name,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _certify(
    ree_layout: ReeLayout,
    *,
    experiment: Experiment,
    basis: EvidenceBasis,
    run_exit_code: int | None,
    observed_verify_exit_code: int | None,
    observed_output_digest: str | None,
    runtime_digest: str | None,
    verify_script_digest: str | None,
) -> ExperimentComparison:
    """Compare the reviewer's run with the author's recorded run of the same name.

    The author's baseline is their selected receipt for this experiment, which
    is keyed by name rather than by operation — an REE has as many of these as
    it has experiments. A baseline that never ran leaves
    ``expected_verify_exit_code`` unset, which the comparison reports as
    inconclusive rather than as agreement.
    """
    author = load_author_receipts(ree_layout).get(experiment_step_key(experiment.name))
    expected_verify_exit_code = None
    expected_output_digest = None
    if isinstance(author, RunExperimentReceipt):
        expected_verify_exit_code = _author_verify_exit_code(author)
        expected_output_digest = author.produced_output_digest

    return compare_experiment_results(
        experiment_name=experiment.name,
        basis=basis,
        verify_script_path=experiment.verify_script,
        verify_script_digest=verify_script_digest,
        expected_verify_exit_code=expected_verify_exit_code,
        observed_verify_exit_code=observed_verify_exit_code,
        run_exit_code=run_exit_code,
        expected_output_digest=expected_output_digest,
        observed_output_digest=observed_output_digest,
        runtime_digest=runtime_digest,
    )


def _author_verify_exit_code(author: RunExperimentReceipt) -> int | None:
    """What the author's own verify script exited, including on older receipts.

    ``verify_exit_code`` post-dates the receipt schema, so REEs authored before
    it record the verdict only in ``status``. That is not a gap: the runnable
    runner sets ``succeeded`` exactly when the run *and* the verify script both
    passed (see :func:`repo2ree_core.execution.experiment.run.run_runnable`), and the
    author receipt store only ever selects successful runs — so a selected
    receipt naming a verify script is the author asserting it exited 0.

    Reading only the literal field would make every REE authored before it
    inconclusive on its most important step, which would report a missing
    schema field as a missing scientific claim.
    """
    if author.verify_exit_code is not None:
        return author.verify_exit_code
    if author.status == "succeeded" and author.verify_script_path.strip():
        return 0
    return None


def _log_verdict(comparison: ExperimentComparison, *, log: LogSink) -> None:
    """Say what the run settled, and — always — which criterion settled it."""
    log(
        "system",
        "info" if comparison.verdict in {"identical", "reproduced"} else "warn",
        f"experiment {comparison.experiment_name!r} {comparison.verdict} ({comparison.basis})",
    )
    if comparison.verdict == "inconclusive" and not comparison.verify_script_path.strip():
        log(
            "system",
            "warn",
            "this experiment declares no verify script, so nothing states what a correct result is — "
            "the run happened, but no verdict about its results can follow from it",
        )
    elif comparison.verdict == "inconclusive":
        log(
            "system",
            "warn",
            "the author never recorded a run of this experiment themselves, so there is no baseline claim to reproduce",
        )
    else:
        log(
            "system",
            "info",
            f"criterion: {comparison.verify_script_path} "
            f"(digest {comparison.verify_script_digest or 'unknown'}), "
            f"author exit {comparison.expected_verify_exit_code}, "
            f"reviewer exit {comparison.observed_verify_exit_code}",
        )
    if comparison.verdict == "reproduced" and comparison.expected_output_digest:
        log(
            "system",
            "info",
            "the declared outputs differ byte for byte, which a passing verify script says is immaterial — "
            "the author's own criterion accepted these results",
        )
    if comparison.basis == "bundled":
        log(
            "system",
            "warn",
            "this result was reproduced against evidence the REE itself carries — it says the shipped "
            "environment still produces an accepted result, not that the recorded origin and recipe do",
        )
