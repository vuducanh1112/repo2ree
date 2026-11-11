"""Run the author's activation alone in the experiment environment a review attempt certified.

The reviewer-side counterpart of the author's ``activation_test`` step, and the
only review step that certifies nothing by comparison: there is no author
artifact to reproduce, so whether the activation enters and hands over is the whole claim.

Two consequences a comparison would otherwise have carried: the ``basis`` is
inherited from the attempt rather than chosen, and the run is bound to the
experiment environment digest the build recorded. An activation that does not hand over *completes*
the step with a ``failed`` verdict; only conditions that stop it running at all
fail the step.
"""

from __future__ import annotations

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.evidence.review.records import review_receipt_envelope
from repo2ree_core.evidence.review.store import write_review_activation_evidence
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.review import (
    CertifiedExperimentEnvironment,
    ReviewRunnableStep,
    open_review_run,
)
from repo2ree_protocol.command import ReviewActivationTestArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import ReviewActivationTestOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest
from repo2ree_ree.model import ReeDefinition
from repo2ree_ree.primitives import WorkspacePath
from repo2ree_ree.review import ActivationOutcome, ActivationVerdict, ReviewActivationReceipt, ReviewRecord


def _select(definition: ReeDefinition) -> tuple[RunnableSpec, str]:
    activation = definition.activate_experiment_environment
    if activation is None:
        raise ValueError("no activate experiment environment script is declared")
    return RunnableSpec(activate_script=str(activation.activate_experiment_environment_script_path)), "activation"


def _admit(_record: ReviewRecord, certified: CertifiedExperimentEnvironment) -> str | None:
    """Unlike an experiment, entering nothing is not a test.

    The activation exists to say the *experiment environment* can be entered, so a baseline that
    declares none has no question here to answer.
    """
    if not certified.experiment_environment_path:
        return "The certified build recorded no experiment environment artifact to activate"
    return None


_STEP = ReviewRunnableStep(
    step="activation",
    noun="review activation",
    subject="activation",
    requires="build_experiment_environment",
    requires_message="Certify the experiment environment before testing the activation",
    experiment_environment_purpose="to activate",
    experiment_environment_retry_purpose="to activate",
    admit=_admit,
    select=_select,
    unresolvable="the author baseline cannot be activated",
    script_noun="an activate experiment environment script",
)


def handle_review_activation_test(
    args: ReviewActivationTestArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_review_run(
        _STEP,
        review_id=args.review_id,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if isinstance(opened, ActionResult):
        return opened

    activation, certified, outcome = opened.runnable, opened.certified, opened.outcome
    verdict: ActivationVerdict = "passed" if outcome.status == "succeeded" else "failed"
    timing = opened.timer.finish()
    # No snapshot digest and no drift verdict, for the same reason the build
    # review records neither: both describe an author's workspace drifting from
    # what it was materialized from, and a review namespace is materialized
    # fresh from its own acquisition every time.
    activate_script_digest = digest_file_if_exists(opened.review_layout.workspace / activation.activate_script)
    if activate_script_digest is None:
        return opened.step.stop("failed", "the activate experiment environment script disappeared after it ran")
    if certified.experiment_environment_digest is None:
        return opened.step.stop("failed", "the certified experiment environment disappeared after activation")
    receipt = ReviewActivationReceipt(
        **review_receipt_envelope(
            run_id,
            timing,
            "succeeded" if outcome.status == "succeeded" else "failed",
        ),
        activate_experiment_environment_script_digest=activate_script_digest,
        exit_code=outcome.run_outputs.exit_code,
        experiment_environment_path=WorkspacePath(certified.experiment_environment_path),
        experiment_environment_digest=Digest(certified.experiment_environment_digest),
    )
    activation_outcome = ActivationOutcome(
        basis=certified.basis,
        verdict=verdict,
        experiment_environment_digest=certified.experiment_environment_digest,
        exit_code=outcome.run_outputs.exit_code,
    )
    write_review_activation_evidence(opened.review_layout, receipt, activation_outcome)
    _log_outcome(activation_outcome, log=log)
    # Completed either way: an activation that will not hand over is this step
    # working, not failing. Recording it as a failure would put the attempt into
    # ``failed`` and lose the difference between "the review could not run" and
    # "the review found the experiment environment uninhabitable".
    opened.step.settle(
        opened.step.record.model_copy(update={"activation_receipt": receipt, "activation_outcome": activation_outcome}),
        timing,
        verdict=verdict,
        basis=certified.basis,
        experiment_environment_digest=certified.experiment_environment_digest,
    )

    outputs = ReviewActivationTestOutputs(
        review_id=args.review_id,
        receipt=receipt,
        outcome=activation_outcome,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _log_outcome(outcome: ActivationOutcome, *, log: LogSink) -> None:
    """Say what the activation settled, and on a failure how it exited."""
    log(
        "system",
        "info" if outcome.verdict == "passed" else "warn",
        f"activation {outcome.verdict} ({outcome.basis}) "
        f"against experiment environment {outcome.experiment_environment_digest or 'none'}",
    )
    if outcome.verdict == "failed":
        log("system", "warn", f"the activation exited {outcome.exit_code}")
    if outcome.basis == "bundled":
        log(
            "system",
            "warn",
            "this activation ran against evidence the REE itself carries — it says that artifact can be entered, "
            "not that the recorded origin and recipe still produce one that can",
        )
