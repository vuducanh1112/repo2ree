"""Reproduce one of the author's experiments inside a review attempt.

The last step of the reviewer lifecycle: source establishes that the code is the
author's, build that the environment is theirs, activation that it comes up, and
this asks whether the result holds.

The verdict is what the author's own verify script says, re-run against the
reviewer's results; matching output digests are a stronger tier where they
happen, never a requirement. Requires activation to have *passed*, not merely
completed. See ``docs/engineering/review-evidence.md``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import Digest, digest_file_if_exists, digest_output_paths
from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.domain.primitives import ScriptPath, WorkspacePath
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.evidence.receipts.models import RunExperimentReceipt, experiment_step_key, receipt_envelope
from repo2ree_core.evidence.receipts.store import load_author_receipts
from repo2ree_core.evidence.review.comparison import compare_experiment_results
from repo2ree_core.evidence.review.models import (
    EvidenceBasis,
    ExperimentComparison,
    ReviewRecord,
    with_experiment,
)
from repo2ree_core.evidence.review.store import write_review_experiment_evidence
from repo2ree_core.execution.experiment.resolve import resolve_experiment_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.review import (
    CertifiedRuntime,
    ReviewRunnableStep,
    open_review_run,
)
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_protocol.command import ReviewRunExperimentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewRunExperimentOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    experiment_name: str
    receipt: RunExperimentReceipt
    comparison: ExperimentComparison


def _admit(record: ReviewRecord, _certified: CertifiedRuntime) -> str | None:
    """A completed activation is not enough — it has to have passed.

    Activation completes with a ``failed`` verdict when the runtime would not
    come up, and every experiment run inside such a runtime would report a
    result failure that is really the activation failure wearing a different
    hat. Recording a wall of ``different`` verdicts would bury the single fact
    that explains them all.
    """
    if record.activation_outcome is None or record.activation_outcome.verdict != "passed":
        return "This attempt's runtime would not come up; its results cannot be reproduced in it"
    return None


def _step(experiment_name: str) -> ReviewRunnableStep[Experiment]:
    """The descriptor for reproducing one named experiment.

    Built per call rather than shared as a constant, because unlike activation
    this step's subject is chosen by the reviewer: the name is what ``select``
    resolves against.
    """

    def select(intent: ReeIntent) -> tuple[Experiment, str]:
        experiment = resolve_experiment_runnable(intent, experiment_name)
        return experiment, experiment.name

    return ReviewRunnableStep(
        step="experiments",
        noun="review experiment",
        subject="the experiment",
        requires="activation",
        requires_message="Probe the runtime before reproducing results in it",
        runtime_purpose="to run experiments in",
        runtime_retry_purpose="to reproduce results",
        admit=_admit,
        select=select,
        unresolvable="the author baseline cannot run this experiment",
        script_noun="a run script",
    )


def handle_review_run_experiment(
    args: ReviewRunExperimentArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_review_run(
        _step(args.experiment_name),
        review_id=args.review_id,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if isinstance(opened, ActionResult):
        return opened

    experiment, certified, outcome = opened.runnable, opened.certified, opened.outcome
    review_layout = opened.review_layout
    run_script_digest = digest_file_if_exists(review_layout.workspace / experiment.run_script)
    verify_script_digest = (
        digest_file_if_exists(review_layout.workspace / experiment.verify_script) if experiment.verify_script else None
    )

    comparison = _certify(
        opened.ree_layout,
        experiment=experiment,
        basis=certified.basis,
        run_exit_code=outcome.run_outputs.exit_code,
        observed_verify_exit_code=outcome.run_outputs.verify_exit_code,
        observed_output_digest=digest_output_paths(review_layout.workspace, experiment.output_paths),
        runtime_digest=certified.runtime_digest,
        # The criterion as it stood in the workspace it ran in. Certification
        # compares this with the author receipt before granting a verdict.
        verify_script_digest=verify_script_digest,
    )

    timing = opened.timer.finish()
    receipt = RunExperimentReceipt(
        **receipt_envelope(run_id, timing, outcome.status),
        experiment_name=experiment.name,
        run_script_path=ScriptPath(experiment.run_script),
        run_script_digest=run_script_digest,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_script_path=ScriptPath(experiment.verify_script) if experiment.verify_script else None,
        verify_script_digest=verify_script_digest,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
        runtime_path=WorkspacePath(certified.runtime_path) if certified.runtime_path else None,
        declared_runtime_digest=Digest(certified.runtime_digest) if certified.runtime_digest else None,
        produced_output_digest=Digest(comparison.observed_output_digest) if comparison.observed_output_digest else None,
    )
    write_review_experiment_evidence(review_layout, receipt, comparison)
    _log_verdict(comparison, log=log)
    # Completed whatever the verdict: an experiment whose results do not
    # reproduce is this step doing its job, and the finding is the most valuable
    # thing a review produces. Only the conditions that stop it running at all
    # are step failures.
    opened.step.settle(
        with_experiment(opened.step.record, receipt, comparison),
        timing,
        verdict=comparison.verdict,
        basis=certified.basis,
        runtime_digest=certified.runtime_digest,
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
    expected_verify_script_digest = None
    expected_output_digest = None
    if isinstance(author, RunExperimentReceipt):
        expected_verify_exit_code = _author_verify_exit_code(author)
        expected_verify_script_digest = author.verify_script_digest
        expected_output_digest = author.produced_output_digest

    return compare_experiment_results(
        experiment_name=experiment.name,
        basis=basis,
        verify_script_path=experiment.verify_script,
        expected_verify_script_digest=expected_verify_script_digest,
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
    if author.status == "succeeded" and author.verify_script_path:
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
    elif comparison.expected_verify_exit_code is None:
        log(
            "system",
            "warn",
            "the author never recorded a run of this experiment themselves, so there is no baseline claim to reproduce",
        )
    elif comparison.expected_verify_script_digest is None:
        log(
            "system",
            "warn",
            "the author's run does not bind its claim to a verify-script digest, so the original criterion "
            "cannot be audited",
        )
    elif comparison.verify_script_digest is None:
        log("system", "warn", "the reviewer could not identify the verify script that ran")
    elif comparison.expected_verify_script_digest != comparison.verify_script_digest:
        log(
            "system",
            "warn",
            "the verify script changed since the author's run: "
            f"expected {comparison.expected_verify_script_digest}, ran {comparison.verify_script_digest}",
        )
    elif comparison.expected_verify_exit_code != 0:
        log(
            "system",
            "warn",
            "the author's own verify script did not accept their baseline result, so there is no accepted claim "
            "to reproduce",
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
