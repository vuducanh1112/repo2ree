from __future__ import annotations

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.evidence.review.records import review_receipt_envelope
from repo2ree_core.evidence.review.store import write_review_activate_experiment_environment_evidence
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.steps.review import (
    CertifiedExperimentEnvironment,
    ReviewRunnableStep,
    open_review_run,
)
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.workspace.attempt import discard
from repo2ree_protocol.command import ReviewActivateExperimentEnvironmentArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import ReviewActivateExperimentEnvironmentOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import ReeDefinition
from repo2ree_ree.primitives import WorkspacePath
from repo2ree_ree.review import (
    ActivationOutcome,
    ActivationVerdict,
    ReviewActivateExperimentEnvironmentReceipt,
    ReviewRecord,
)


def _select(definition: ReeDefinition) -> tuple[RunnableSpec, str]:
    activation = definition.activate_experiment_environment
    return RunnableSpec(activate_script=str(activation.activate_experiment_environment_script_path)), "activation"


def _admit(_record: ReviewRecord, certified: CertifiedExperimentEnvironment) -> str | None:
    if not certified.experiment_environment_path:
        return "The certified build recorded no experiment environment artifact to activate"
    return None


_STEP = ReviewRunnableStep(
    step="activate_experiment_environment",
    noun="review activation",
    subject="activation",
    requires="build_experiment_environment",
    requires_message="Certify the experiment environment before testing the activation",
    experiment_environment_purpose="to activate",
    admit=_admit,
    select=_select,
    unresolvable="the author baseline cannot be activated",
    script_noun="an activate experiment environment script",
)


def handle_review_activate_experiment_environment(
    args: ReviewActivateExperimentEnvironmentArgs,
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_review_run(
        _STEP,
        layout=layout,
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
    activate_script_digest = digest_file_if_exists(opened.workspace / activation.activate_script)
    if activate_script_digest is None:
        return opened.step.stop("failed", "the activate experiment environment script disappeared after it ran")
    receipt = ReviewActivateExperimentEnvironmentReceipt(
        **review_receipt_envelope(
            run_id,
            timing,
            "succeeded" if outcome.status == "succeeded" else "failed",
        ),
        activate_experiment_environment_script_digest=activate_script_digest,
        exit_code=outcome.run_outputs.exit_code,
        experiment_environment_path=WorkspacePath(certified.experiment_environment_path),
        experiment_environment_digest=certified.experiment_environment_digest,
        launch_script_digest=opened.launch_script_digest,
        launched=outcome.launched,
    )
    activation_outcome = ActivationOutcome(
        basis=certified.basis,
        verdict=verdict,
        experiment_environment_digest=certified.experiment_environment_digest,
        exit_code=outcome.run_outputs.exit_code,
    )
    write_review_activate_experiment_environment_evidence(opened.review_layout, receipt, activation_outcome)
    _log_outcome(activation_outcome, log=log)
    opened.step.settle(
        opened.step.record.model_copy(
            update={
                "receipts": opened.step.record.receipts.model_copy(update={"activate_experiment_environment": receipt}),
                "activation_outcome": activation_outcome,
            }
        ),
        timing,
        verdict=verdict,
        basis=certified.basis,
        experiment_environment_digest=certified.experiment_environment_digest,
    )
    discard(opened.review_layout, run_id)

    outputs = ReviewActivateExperimentEnvironmentOutputs(
        review_id=args.review_id,
        receipt=receipt,
        outcome=activation_outcome,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _log_outcome(outcome: ActivationOutcome, *, log: LogSink) -> None:
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
