"""Probe the runtime a review attempt certified, inside that attempt's workspace.

The reviewer-side counterpart of the author's ``activation_test`` step, and the
only review step that certifies nothing by comparison: there is no author
artifact to reproduce, so the reviewer's own probe is the whole claim.

Two consequences a comparison would otherwise have carried: the ``basis`` is
inherited from the attempt rather than chosen, and the probe is bound to the
runtime digest the build recorded. A runtime that does not come up *completes*
the step with a ``failed`` verdict; only conditions that stop it probing at all
fail the step. See ``docs/engineering/review-evidence.md``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import Digest, digest_file_if_exists
from repo2ree_core.domain.primitives import ReePath, WorkspacePath
from repo2ree_core.domain.ree.model import ReeDefinition
from repo2ree_core.evidence.review.models import (
    ActivationOutcome,
    ActivationVerdict,
    ReviewActivationReceipt,
    ReviewRecord,
    review_receipt_envelope,
)
from repo2ree_core.evidence.review.store import write_review_activation_evidence
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.review import (
    CertifiedRuntime,
    ReviewRunnableStep,
    open_review_run,
)
from repo2ree_protocol.command import ReviewActivationTestArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewActivationTestOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewActivationReceipt
    outcome: ActivationOutcome


def _select(definition: ReeDefinition) -> tuple[RunnableSpec, str]:
    activation = definition.test_activation
    if activation is None:
        raise ValueError("no activation test is declared")
    return (
        RunnableSpec(
            run_script=str(activation.run_script_path),
            verify_script=str(activation.verify_script_path or ""),
        ),
        "activation",
    )


def _admit(_record: ReviewRecord, certified: CertifiedRuntime) -> str | None:
    """Unlike an experiment, a probe of nothing is not a probe.

    Activation exists to say the *runtime* comes up, so a baseline that declares
    none has no question here to answer.
    """
    if not certified.runtime_path:
        return "The certified build recorded no runtime artifact to activate"
    return None


_STEP = ReviewRunnableStep(
    step="activation",
    noun="review activation",
    subject="activation",
    requires="build",
    requires_message="Certify the runtime before probing whether it is inhabitable",
    runtime_purpose="to activate",
    runtime_retry_purpose="to activate",
    admit=_admit,
    select=_select,
    unresolvable="the author baseline cannot be activated",
    script_noun="an activation script",
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
    run_script_digest = digest_file_if_exists(opened.review_layout.workspace / activation.run_script)
    if run_script_digest is None:
        return opened.step.stop("failed", "the activation script disappeared after it ran")
    if certified.runtime_digest is None:
        return opened.step.stop("failed", "the certified runtime disappeared after activation")
    verify_script_digest = (
        digest_file_if_exists(opened.review_layout.workspace / activation.verify_script)
        if activation.verify_script
        else None
    )
    receipt = ReviewActivationReceipt(
        **review_receipt_envelope(
            run_id,
            timing,
            "succeeded" if outcome.status == "succeeded" else "failed",
        ),
        run_script_path=ReePath(activation.run_script),
        run_script_digest=run_script_digest,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_script_path=ReePath(activation.verify_script) if activation.verify_script else None,
        verify_script_digest=verify_script_digest,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
        runtime_path=WorkspacePath(certified.runtime_path),
        runtime_digest=Digest(certified.runtime_digest),
    )
    activation_outcome = ActivationOutcome(
        basis=certified.basis,
        verdict=verdict,
        runtime_digest=certified.runtime_digest,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
    )
    write_review_activation_evidence(opened.review_layout, receipt, activation_outcome)
    _log_outcome(activation_outcome, log=log)
    # Completed either way: a runtime that will not come up is this step
    # working, not failing. Recording it as a failure would put the attempt into
    # ``failed`` and lose the difference between "the review could not run" and
    # "the review found the runtime uninhabitable".
    opened.step.settle(
        opened.step.record.model_copy(update={"activation_receipt": receipt, "activation_outcome": activation_outcome}),
        timing,
        verdict=verdict,
        basis=certified.basis,
        runtime_digest=certified.runtime_digest,
    )

    outputs = ReviewActivationTestOutputs(
        review_id=args.review_id,
        receipt=receipt,
        outcome=activation_outcome,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _log_outcome(outcome: ActivationOutcome, *, log: LogSink) -> None:
    """Say what the probe settled, and — on a failure — which half settled it."""
    log(
        "system",
        "info" if outcome.verdict == "passed" else "warn",
        f"activation {outcome.verdict} ({outcome.basis}) against runtime {outcome.runtime_digest or 'none'}",
    )
    if outcome.verdict == "failed":
        log(
            "system",
            "warn",
            f"run script exited {outcome.run_exit_code}, "
            f"verify script exited {outcome.verify_exit_code if outcome.verify_exit_code is not None else 'not run'}",
        )
    if outcome.basis == "bundled":
        log(
            "system",
            "warn",
            "this probe ran against evidence the REE itself carries — it says that artifact is inhabitable, "
            "not that the recorded origin and recipe still produce one that is",
        )
