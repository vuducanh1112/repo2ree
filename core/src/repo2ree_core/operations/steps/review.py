"""Machinery shared by the reviewer-side step handlers.

A review step writes into a parallel REE tree, and every way it can stop has to
leave that tree's record consistent with what happened. This module owns the
step preamble, both of a step's exits (:class:`ReviewStep`), and the guards that
run before a step is marked running.

The ``require_*`` / ``open_*`` helpers return either their value or the
``ActionResult`` the caller returns unchanged; guard-only helpers return
``ActionResult | None``. Design rationale: ``docs/engineering/explanation/step-lifecycle.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.ree.model import Ree, ReeDefinition
from repo2ree_core.evidence.review.models import (
    ActivationVerdict,
    BuildVerdict,
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentVerdict,
    ReviewBuildRuntimeReceipt,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
    attempt_basis,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import read_review_record, write_review_record
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import ARTIFACTS_DIRNAME, ReeLayout, ReviewLayout
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms, format_utc_instant
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import ReviewStepAttrs

# Signature of the per-handler early exit: a terminal status and why.
ReviewHalt = Callable[[ReviewStatus, str], ActionResult]

# What a completed step settled. The four vocabularies are disjoint apart from
# ``identical``; the union is what the shared exit accepts, so a step cannot
# report a verdict from a lifecycle it does not belong to.
ReviewVerdict = ComparisonVerdict | BuildVerdict | ActivationVerdict | ExperimentVerdict


class ReviewSettle(Protocol):
    """Signature of the per-handler success exit.

    A protocol rather than a ``Callable[...]`` alias so the optional keyword
    arguments stay checked — a typo in one would otherwise be silently dropped
    from the span.
    """

    def __call__(
        self,
        record: ReviewRecord,
        timing: OperationTiming,
        *,
        verdict: ReviewVerdict | None = None,
        basis: EvidenceBasis | None = None,
        runtime_digest: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class ReviewStep:
    """A started review step: the record it began from, and the two ways it ends.

    ``record`` is the *started* record, which every later write must build on —
    a handler that kept the pre-start record would persist a step whose status
    contradicts what the exit already wrote.

    ``stop`` and ``settle`` are closures over this step's identity held as
    fields rather than methods, so they cannot be called with a different one.
    """

    record: ReviewRecord
    stop: ReviewHalt
    settle: ReviewSettle


def require_ree_baseline(ree_layout: ReeLayout, *, log: LogSink) -> Ree | ActionResult:
    """The author baseline this attempt reviews, or the failure to return.

    Read *before* the step is marked running: a baseline nobody can read is a
    precondition nobody can meet, so there is nothing to mark running and
    nothing to settle a halt on.
    """
    store = ReeDirectory(ree_layout)
    if not store.manifest_exists():
        message = "This workbench holds no REE to review"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)
    try:
        return store.read_ree()
    except UNREADABLE_DOCUMENT as exc:
        # A precondition rather than an `internal` fault: the document is the
        # REE's, not this code's, so the reviewer's next action is to fix the
        # baseline rather than to report a bug.
        message = f"The REE under review has unreadable metadata: {exc}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)


def require_review_record(review_layout: ReviewLayout, review_id: str, log: LogSink) -> ReviewRecord | ActionResult:
    """The attempt this step joins, or the failure to return when there is none.

    Only the source step opens an attempt; every later step joins one, so "no
    such attempt" is the same precondition failure for all of them. Halts
    *before* :func:`begin_review_step`, for the reason given there.
    """
    record = read_review_record(review_layout)
    if record is not None:
        return record
    message = f"No review attempt named {review_id}"
    log("system", "error", message)
    return ActionResult.failed("precondition", message)


def begin_review_step(
    review_layout: ReviewLayout,
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    review_id: str,
    timer: OperationTimer,
    log: LogSink,
    noun: str,
) -> ReviewStep:
    """Mark a step running on the persisted record and arm both of its exits.

    The record is written *before* any work, so an attempt killed mid-step reads
    as a step that started rather than one that never ran. The step's identity
    goes on the span here rather than at either exit, for the same reason.
    """
    started = with_step(record, step, status="running", at=format_utc_instant(timer.started_at))
    write_review_record(review_layout, started)
    ReviewStepAttrs(review_id=review_id, step=step).apply_current()
    return ReviewStep(
        record=started,
        stop=_review_step_halt(
            review_layout=review_layout,
            record=started,
            step=step,
            review_id=review_id,
            timer=timer,
            log=log,
            noun=noun,
        ),
        settle=_review_step_settle(
            review_layout=review_layout,
            step=step,
            log=log,
            noun=noun,
        ),
    )


def _review_step_halt(
    *,
    review_layout: ReviewLayout,
    record: ReviewRecord,
    step: ReviewStepKey,
    review_id: str,
    timer: OperationTimer,
    log: LogSink,
    noun: str,
) -> ReviewHalt:
    """Build the "this step could not run" exit: canceled, precondition, nonzero.

    Settles the step on the persisted record, logs it, and returns a result that
    agrees with both. *Not* for a step that ran to completion and found
    something unwelcome — those settle with a verdict through
    :func:`_review_step_settle`.
    """

    def halt(status: ReviewStatus, message: str) -> ActionResult:
        timing = timer.finish()
        write_review_record(
            review_layout,
            with_step(record, step, status=status, at=format_utc_instant(timing.finished_at), failure=message),
        )
        ReviewStepAttrs(step=step, status=status).apply_current()
        log("system", "warn" if status == "canceled" else "error", f"{noun} {status}: {message}")
        if status == "canceled":
            return ActionResult(status="canceled", outputs={"review_id": review_id})
        return ActionResult.failed("precondition", message)

    return halt


def _review_step_settle(
    *,
    review_layout: ReviewLayout,
    step: ReviewStepKey,
    log: LogSink,
    noun: str,
) -> ReviewSettle:
    """Build the "this step ran to completion" exit for one review step.

    Settles ``completed`` whatever the verdict — the verdict is the handler's
    business, not this one's.

    The handler passes the record already carrying this step's evidence together
    with the ``timing`` that evidence was stamped with, so the record can never
    claim a duration its own receipt contradicts.
    """

    def settle(
        record: ReviewRecord,
        timing: OperationTiming,
        *,
        verdict: ReviewVerdict | None = None,
        basis: EvidenceBasis | None = None,
        runtime_digest: str | None = None,
    ) -> None:
        write_review_record(
            review_layout,
            with_step(record, step, status="completed", at=format_utc_instant(timing.finished_at)),
        )
        ReviewStepAttrs(
            step=step,
            status="completed",
            verdict=verdict,
            basis=basis,
            runtime_digest=runtime_digest,
        ).apply_current()
        log(
            "system",
            "info",
            f"{noun} completed in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )

    return settle


def require_completed_step(
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    stop: ReviewHalt,
    message: str,
) -> ActionResult | None:
    """Halt unless the step this one builds on has completed.

    The review lifecycle is a chain: source, build, activation, experiments.
    ``message`` should say what to do about it rather than restate the graph — a
    client that called out of order needs the next action, not the topology.
    """
    state = step_state(record, step)
    if state is None or state.status != "completed":
        return stop("failed", message)
    return None


@dataclass(frozen=True)
class CertifiedRuntime:
    """The runtime a review attempt certified, confirmed still to be that one.

    ``runtime_path`` is empty for a baseline that declares no runtime artifact (a
    native experiment), in which case ``runtime_digest`` is None. Reports what
    the attempt has, not what a caller needs — steps that cannot run without a
    runtime say so themselves.
    """

    basis: EvidenceBasis
    build_receipt: ReviewBuildRuntimeReceipt
    runtime_path: str
    runtime_digest: str | None


def require_certified_runtime(
    record: ReviewRecord,
    review_layout: ReviewLayout,
    *,
    stop: ReviewHalt,
    purpose: str,
    retry_purpose: str,
) -> CertifiedRuntime | ActionResult:
    """The apparatus every post-build review step runs against, or the halt.

    Checks the three things that must hold before a step runs *inside* what the
    build left behind: the attempt settled a basis and a build receipt, its
    workspace is still there, and the runtime in that workspace is byte-for-byte
    the one the build certified.

    ``purpose`` completes "This attempt has recorded no runtime …" and
    ``retry_purpose`` completes "… re-run the build review …", so each step says
    what *it* was trying to do.
    """
    basis = attempt_basis(record)
    if basis is None or record.build_receipt is None:
        return stop("failed", f"This attempt has recorded no runtime {purpose}")

    # Reclaiming the workspace is a supported choice at build time, so hitting
    # this is the reviewer's own doing: say how to undo it rather than reporting
    # a bare missing path.
    if not review_layout.workspace.is_dir():
        return stop(
            "failed",
            f"This attempt's workspace was reclaimed after the build; re-run the build review {retry_purpose}",
        )

    runtime_path = (record.build_receipt.runtime_path or "").strip()
    runtime = workspace_runtime(review_layout, runtime_path) if runtime_path else None
    runtime_digest = digest_file_if_exists(runtime) if runtime else None
    if runtime_path and runtime_digest is None:
        return stop("failed", f"the certified runtime is no longer in this attempt's workspace at {runtime_path}")
    if runtime_path and runtime_digest != record.build_receipt.produced_runtime_digest:
        return stop(
            "failed",
            f"the runtime at {runtime_path} is not the one this attempt certified; re-run the build review",
        )

    return CertifiedRuntime(
        basis=basis,
        build_receipt=record.build_receipt,
        runtime_path=runtime_path,
        runtime_digest=runtime_digest,
    )


def workspace_runtime_candidates(layout: ReeLayout, runtime_path: str) -> tuple[Path, ...]:
    """Where a runtime can sit in a materialized workspace, declared path first.

    Normally there is one answer. The exception is a baseline loaded from a
    bundle: packaging lifted the runtime into ``artifacts/`` and rewrote the
    declared path to ``artifacts/<basename>``, discarding the workspace path the
    build script writes to. The remap keeps the basename, so undoing it is a
    lookup rather than a guess.

    Takes any REE root rather than a review layout: nothing here is the
    reviewer's, and an author's workspace loaded from a bundle carries the same
    remap.
    """
    declared = layout.workspace / runtime_path
    parts = PurePosixPath(runtime_path).parts
    if len(parts) == 2 and parts[0] == ARTIFACTS_DIRNAME:
        return (declared, layout.workspace / parts[1])
    return (declared,)


def workspace_runtime(layout: ReeLayout, runtime_path: str) -> Path:
    """The runtime in a materialized workspace, wherever it legitimately landed.

    Falls back to the declared path when none of the candidates exist, so a miss
    is reported against the path the author declared rather than against a
    fallback the author never named.
    """
    candidates = workspace_runtime_candidates(layout, runtime_path)
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


# ================================================
# Running one of the author's runnables
# ================================================


#: An extra precondition a step has that the others do not, checked once the
#: certified runtime is in hand. Returns the refusal message, or None to admit.
ReviewAdmission = Callable[[ReviewRecord, CertifiedRuntime], str | None]


@dataclass(frozen=True)
class ReviewRunnableStep:
    """What distinguishes the two review steps that run one of the author's runnables.

    Covers how a step *gets to* its run and stops there; what each handler does
    with the outcome stays in the handler. See
    ``docs/engineering/explanation/step-lifecycle.md``.

    ``admit`` is the one genuinely per-step precondition — activation needs a
    runtime artifact to probe, an experiment needs an activation that passed. It
    runs after certification, so both steps report the apparatus being absent
    before reporting what they wanted it for.
    """

    step: ReviewStepKey
    #: Completes the log line: "<noun> completed in …", "<noun> failed: …".
    noun: str
    #: Names the step in cancellation messages: "canceled before <subject>".
    subject: str
    requires: ReviewStepKey
    requires_message: str
    runtime_purpose: str
    runtime_retry_purpose: str
    admit: ReviewAdmission
    #: Resolve the runnable this step runs, and the label it runs under. Raises
    #: ``ValueError`` when the baseline cannot produce it.
    select: Callable[[ReeDefinition], tuple[RunnableSpec, str]]
    #: Completes "<unresolvable>: <why>" when ``select`` refuses.
    unresolvable: str
    #: Completes "the author baseline declares <script_noun> that is not there".
    script_noun: str


@dataclass(frozen=True)
class ReviewRun:
    """One of the author's runnables, resolved and run inside a review attempt.

    Everything a handler needs to judge what just happened and settle it: the
    trees to read and write, the step's two exits, the runtime the run is bound
    to, and the run's own outcome. The handler owns everything from here on.
    """

    ree_layout: ReeLayout
    review_layout: ReviewLayout
    step: ReviewStep
    timer: OperationTimer
    certified: CertifiedRuntime
    runnable: RunnableSpec
    label: str
    outcome: ExperimentRunOutcome


def open_review_run(
    step: ReviewRunnableStep,
    *,
    review_id: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ReviewRun | ActionResult:
    """Take a review step from its command up to the end of its run.

    Returns the run for the handler to judge, or the ``ActionResult`` to return
    unchanged — every refusal below has already settled the attempt's record and
    said why.
    """
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(ree_layout, log=log)
    if isinstance(ree, ActionResult):
        return ree

    record = require_review_record(review_layout, review_id, log)
    if isinstance(record, ActionResult):
        return record

    started = begin_review_step(
        review_layout,
        record,
        step.step,
        review_id=review_id,
        timer=timer,
        log=log,
        noun=step.noun,
    )

    if is_canceled():
        return started.stop("canceled", f"canceled before {step.subject}")

    halted = require_completed_step(started.record, step.requires, stop=started.stop, message=step.requires_message)
    if halted is not None:
        return halted

    certified = require_certified_runtime(
        started.record,
        review_layout,
        stop=started.stop,
        purpose=step.runtime_purpose,
        retry_purpose=step.runtime_retry_purpose,
    )
    if isinstance(certified, ActionResult):
        return certified

    refusal = step.admit(started.record, certified)
    if refusal is not None:
        return started.stop("failed", refusal)

    try:
        runnable, label = step.select(ree.subject.definition)
    except ValueError as exc:
        return started.stop("failed", f"{step.unresolvable}: {exc}")

    # Absent apparatus is a fact about the baseline, not a verdict about it:
    # fail the step rather than settle a verdict nothing ever exercised.
    if not (review_layout.workspace / runnable.run_script).is_file():
        return started.stop(
            "failed",
            f"the author baseline declares {step.script_noun} that is not there: {runnable.run_script}",
        )

    outcome = run_runnable(
        workspace=review_layout.workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled" or is_canceled():
        return started.stop("canceled", f"{step.subject} was canceled")

    return ReviewRun(
        ree_layout=ree_layout,
        review_layout=review_layout,
        step=started,
        timer=timer,
        certified=certified,
        runnable=runnable,
        label=label,
        outcome=outcome,
    )
