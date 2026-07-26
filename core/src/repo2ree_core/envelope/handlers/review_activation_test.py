"""Probe the runtime a review attempt certified, inside that attempt's workspace.

The reviewer-side counterpart of the author's ``activation_test`` step, and the
first review step that certifies nothing by comparison. Source has the author's
SWHID and build has their SBOM closure — both recorded artifacts a reviewer can
reproduce and diff. Activation has no such artifact. The author's own activation
receipt is a precondition of a credible baseline, not a baseline to reproduce:
"their probe passed and so did mine" says nothing the second half does not
already say. So this step runs the author's activation script against the
reviewer's own runtime and reports whether it came up, full stop.

That makes two things load-bearing that a comparison would otherwise have
carried:

*Basis* is inherited, not chosen. Activation runs in the workspace the build
left behind and deliberately cannot tell whether the runtime there was rebuilt
or unpacked from the bundle — that indifference is what lets the author's
scripts run unchanged on either basis. So it takes no ``basis`` argument and
adopts the weakest one the attempt has settled: passing on a shipped artifact
says that artifact is inhabitable, never that the world still produces one.

*Identity* is checked, not assumed. The probe is bound to the runtime digest the
build step recorded, so an attempt whose build has since been re-run cannot
leave a pass attached to a runtime that no longer exists. This mirrors the
author-side scorecard, which likewise only counts an activation pass against the
runtime that was actually built.

A runtime that does not come up completes the step with a ``failed`` verdict
rather than failing it. The distinction matters: the reviewer's machine did
exactly its job, and the finding is the most valuable thing this step can
produce. Only the conditions that stop it probing at all — a reclaimed
workspace, no activation script, a stale runtime — fail the step, and they are
statements about the attempt rather than about the runtime.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.envelope.handlers._review_common import review_step_halt, workspace_runtime
from repo2ree_core.experiment.resolve import RunnableResolutionError, resolve_activation_runnable
from repo2ree_core.experiment.run import run_runnable
from repo2ree_core.receipts import ActivationTestReceipt, receipt_run_id
from repo2ree_core.reviews import (
    ActivationOutcome,
    ActivationVerdict,
    attempt_basis,
    read_review_record,
    step_state,
    with_step,
    write_review_activation_evidence,
    write_review_record,
)
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import ReviewActivationTestArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewActivationTestOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ActivationTestReceipt
    outcome: ActivationOutcome


def handle_review_activation_test(
    args: ReviewActivationTestArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(args.review_id)
    timer = OperationTimer.start()

    record = read_review_record(review_layout)
    if record is None:
        message = f"No review attempt named {args.review_id}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)

    started = with_step(record, "activation", status="running", at=timer.started_at)
    write_review_record(review_layout, started)

    stop = review_step_halt(
        review_layout=review_layout,
        record=started,
        step="activation",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review activation",
    )

    if is_canceled():
        return stop("canceled", "canceled before activation")

    build = step_state(started, "build")
    if build is None or build.status != "completed":
        return stop("failed", "Certify the runtime before probing whether it is inhabitable")

    basis = attempt_basis(started)
    if basis is None or started.build_receipt is None:
        return stop("failed", "This attempt has recorded no runtime to activate")

    # The workspace is the whole apparatus here: the reviewer's source, the
    # author's recipe, and the runtime beside them. Reclaiming it is a supported
    # choice at build time, so hitting this is a reviewer's own doing and the
    # message says how to undo it rather than reporting a bare missing path.
    if not review_layout.workspace.is_dir():
        return stop(
            "failed",
            "This attempt's workspace was reclaimed after the build; re-run the build review to activate",
        )

    runtime_path = (started.build_receipt.runtime_path or "").strip()
    if not runtime_path:
        return stop("failed", "The certified build recorded no runtime artifact to activate")

    # Bind the probe to the artifact the build step certified. Without this a
    # re-run build would leave the earlier pass standing over a runtime that is
    # no longer there — a verdict about bytes nobody can point to.
    runtime_abs = workspace_runtime(review_layout, runtime_path)
    runtime_digest = digest_file_if_exists(runtime_abs)
    if runtime_digest is None:
        return stop("failed", f"the certified runtime is no longer in this attempt's workspace at {runtime_path}")
    if runtime_digest != started.build_receipt.produced_runtime_digest:
        return stop(
            "failed",
            f"the runtime at {runtime_path} is not the one this attempt certified; re-run the build review",
        )

    try:
        activation = resolve_activation_runnable(ReeStore(ree_layout).read_intent())
    except RunnableResolutionError as exc:
        return stop("failed", f"the author baseline cannot be activated: {exc}")

    # A script that is not there would otherwise run, fail, and be recorded as
    # "the runtime would not come up" — a verdict about a runtime nothing ever
    # probed. Absent apparatus is a fact about the baseline, so it fails the step.
    if not (review_layout.workspace / activation.run_script).is_file():
        return stop(
            "failed",
            f"the author baseline declares an activation script that is not there: {activation.run_script}",
        )

    outcome = run_runnable(
        workspace=review_layout.workspace.resolve(),
        runnable=activation,
        label="activation",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled" or is_canceled():
        return stop("canceled", "activation canceled")

    verdict: ActivationVerdict = "passed" if outcome.status == "succeeded" else "failed"
    timing = timer.finish()
    # No snapshot digest and no drift verdict, for the same reason the build
    # review records neither: both describe an author's workspace drifting from
    # what it was materialized from, and a review namespace is materialized
    # fresh from its own acquisition every time.
    receipt = ActivationTestReceipt(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status=outcome.status,
        run_script_path=activation.run_script,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_script_path=activation.verify_script,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
        runtime_path=runtime_path,
        declared_runtime_digest=runtime_digest,
    )
    activation_outcome = ActivationOutcome(
        basis=basis,
        verdict=verdict,
        runtime_digest=runtime_digest,
        run_exit_code=outcome.run_outputs.exit_code,
        verify_exit_code=outcome.run_outputs.verify_exit_code,
    )
    write_review_activation_evidence(review_layout, receipt, activation_outcome)
    write_review_record(
        review_layout,
        with_step(
            started.model_copy(update={"activation_receipt": receipt, "activation_outcome": activation_outcome}),
            "activation",
            # Completed either way: a runtime that will not come up is this step
            # working, not failing. Recording it as a failure would put the
            # attempt into ``failed`` and lose the difference between "the review
            # could not run" and "the review found the runtime uninhabitable".
            status="completed",
            at=timing.finished_at,
        ),
    )
    _log_outcome(activation_outcome, log=log)
    log(
        "system",
        "info",
        f"review activation completed in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
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
