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

import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from repo2ree_core.digests import digest_file, digest_tree
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.evidence.review.records import attempt_basis, step_state, with_step
from repo2ree_core.evidence.review.store import read_review_record, write_review_record
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.launch import Launch, declared_launch
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_core.workspace.attempt import environment_in_workspace, fresh, overlay_onto
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest
from repo2ree_ree.model import Ree, ReeDefinition
from repo2ree_ree.review import (
    ActivationVerdict,
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentEnvironmentVerdict,
    ExperimentVerdict,
    ReviewBuildExperimentEnvironmentReceipt,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
)
from repo2ree_ree.signature import review_signature_path
from repo2ree_telemetry.spans import ReviewStepAttrs

# Signature of the per-handler early exit: a terminal status and why.
ReviewHalt = Callable[[ReviewStatus, str], ActionResult]

# What a completed step settled. The four vocabularies are disjoint apart from
# ``identical``; the union is what the shared exit accepts, so a step cannot
# report a verdict from a lifecycle it does not belong to.
ReviewVerdict = ComparisonVerdict | ExperimentEnvironmentVerdict | ActivationVerdict | ExperimentVerdict


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
        experiment_environment_digest: str | None = None,
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
    if record is None:
        message = f"No review attempt named {review_id}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)
    if (refused := refuse_signed_review(review_layout, review_id, log)) is not None:
        return refused
    return record


def refuse_signed_review(review_layout: ReviewLayout, review_id: str, log: LogSink) -> ActionResult | None:
    """The failure to return for a signed review: it changes no more, so no step runs in it, nor reopens it."""
    if not (review_layout.root / review_signature_path()).is_file():
        return None
    message = f"Review {review_id} is signed, and a signed review changes no more: open a new review"
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
    started = with_step(record, step, status="running", at=timer.started_at)
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
            with_step(record, step, status=status, at=timing.finished_at, failure=message),
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
        experiment_environment_digest: str | None = None,
    ) -> None:
        write_review_record(
            review_layout,
            with_step(record, step, status="completed", at=timing.finished_at),
        )
        ReviewStepAttrs(
            step=step,
            status="completed",
            verdict=verdict,
            basis=basis,
            experiment_environment_digest=experiment_environment_digest,
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
class CertifiedExperimentEnvironment:
    """The experiment environment a review attempt certified, as its build receipt records it.

    That the file kept beside the review is still this one is checked where a step lays out its workspace.
    """

    basis: EvidenceBasis
    experiment_environment_receipt: ReviewBuildExperimentEnvironmentReceipt
    experiment_environment_path: str
    experiment_environment_digest: Digest


def require_certified_experiment_environment(
    record: ReviewRecord,
    *,
    stop: ReviewHalt,
    purpose: str,
) -> CertifiedExperimentEnvironment | ActionResult:
    """The apparatus every post-build review step runs against, or the halt.

    ``purpose`` completes "This attempt has recorded no experiment environment …", so each step says what *it* was
    trying to do.
    """
    basis = attempt_basis(record)
    receipt = record.receipts.build_experiment_environment
    if basis is None or receipt is None:
        return stop("failed", f"This attempt has recorded no experiment environment {purpose}")
    return CertifiedExperimentEnvironment(
        basis=basis,
        experiment_environment_receipt=receipt,
        experiment_environment_path=str(receipt.artifact_path),
        experiment_environment_digest=receipt.produced_artifact_digest,
    )


# ================================================
# The workspace a review step runs in
# ================================================


def _review_source(review: ReviewLayout, record: ReviewRecord, workspace: Path) -> None:
    receipt = record.receipts.acquire_source
    if receipt is None or receipt.observed_swhid is None:
        raise ReePreconditionError("this review has recorded no source it acquired")
    if not review.upstream.is_dir() or directory_swhid(review.upstream) != receipt.observed_swhid:
        raise ReePreconditionError("the source in this review is not the one its acquisition observed")
    shutil.copytree(review.upstream, workspace, symlinks=True, dirs_exist_ok=True)


def _review_overlay(review: ReviewLayout, record: ReviewRecord) -> None:
    build = record.receipts.build_experiment_environment
    if build is None:
        raise ReePreconditionError("this review has certified no experiment environment")
    if digest_tree(review.overlay) != build.overlay_digest:
        raise ReePreconditionError("the overlay in this review is not the one its build copied")


def _review_environment(review: ReviewLayout, record: ReviewRecord, workspace: Path) -> None:
    build = record.receipts.build_experiment_environment
    if build is None:
        raise ReePreconditionError("this review has certified no experiment environment")
    declared = str(build.artifact_path)
    kept = review.kept_environment(declared)
    if not kept.is_file():
        raise ReePreconditionError(f"the experiment environment this review certified is missing: {declared}")
    if digest_file(kept) != build.produced_artifact_digest:
        raise ReePreconditionError(f"the experiment environment at {declared} is not the one this review certified")
    target = environment_in_workspace(workspace, declared)[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kept, target)


def lay_out_review(review: ReviewLayout, record: ReviewRecord, run_id: str, *, after_build: bool) -> Path:
    """A fresh workspace for the review attempt ``run_id``: the source as the review's acquisition observed it and the
    overlay the review holds over it; ``after_build``, that overlay as the review's build copied it and the experiment
    environment the build certified, where the author's scripts look for it. Raises ReePreconditionError when what
    the review records is not there as it records it."""
    workspace = fresh(review, run_id)
    _review_source(review, record, workspace)
    if after_build:
        _review_overlay(review, record)
    overlay_onto(review, workspace)
    if after_build:
        _review_environment(review, record, workspace)
    return workspace


# ================================================
# Running one of the author's runnables
# ================================================


#: An extra precondition a step has that the others do not, checked once the
#: certified experiment environment is in hand. Returns the refusal message, or None to admit.
ReviewAdmission = Callable[[ReviewRecord, CertifiedExperimentEnvironment], str | None]


def review_launch(record: ReviewRecord, ree: Ree, workspace: Path) -> Launch | None:
    """How this attempt launches the author's scripts in ``workspace``: as the reviewer chose, and only through the
    launch script the author declares. Raises ``ReePreconditionError`` when the author's copy is not that script."""
    if record.launch.mode == "native":
        return None
    return declared_launch(ree.subject.definition.launch, workspace, record.launch.options)


def launch_digest(ree: Ree, launch: Launch | None) -> Digest | None:
    """The digest of the author's launch script a step ran under; None when it ran natively."""
    return ree.subject.definition.launch.launch_script_digest if launch is not None else None


@dataclass(frozen=True)
class ReviewRunnableStep:
    """What distinguishes the two review steps that run one of the author's runnables.

    Covers how a step *gets to* its run and stops there; what each handler does
    with the outcome stays in the handler. See
    ``docs/engineering/explanation/step-lifecycle.md``.

    ``admit`` is the one genuinely per-step precondition — activation needs an
    experiment environment artifact to enter, an experiment needs an activation that passed. It
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
    experiment_environment_purpose: str
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
    trees to read and write, the step's two exits, the experiment environment the run is bound
    to, and the run's own outcome. The handler owns everything from here on.
    """

    ree_layout: ReeLayout
    review_layout: ReviewLayout
    # Where the run ran, laid out for it alone; discarded once the handler has settled the step.
    workspace: Path
    step: ReviewStep
    timer: OperationTimer
    certified: CertifiedExperimentEnvironment
    runnable: RunnableSpec
    label: str
    outcome: ExperimentRunOutcome
    # The author's launch script the run went through; None when it ran directly.
    launch_script_digest: Digest | None


def open_review_run(
    step: ReviewRunnableStep,
    *,
    layout: ReeLayout,
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
    review_layout = layout.review(review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(layout, log=log)
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

    certified = require_certified_experiment_environment(
        started.record,
        stop=started.stop,
        purpose=step.experiment_environment_purpose,
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

    try:
        workspace = lay_out_review(review_layout, started.record, run_id, after_build=True)
    except ReePreconditionError as exc:
        return started.stop("failed", f"cannot lay out a workspace {step.experiment_environment_purpose}: {exc}")

    # Absent apparatus is a fact about the baseline, not a verdict about it:
    # fail the step rather than settle a verdict nothing ever exercised.
    script = runnable.run_script or runnable.activate_script
    if not (workspace / script).is_file():
        return started.stop(
            "failed",
            f"the author baseline declares {step.script_noun} that is not there: {script}",
        )

    try:
        launch = review_launch(started.record, ree, workspace)
    except ReePreconditionError as exc:
        return started.stop("failed", f"cannot launch the author's scripts: {exc}")
    runnable = replace(runnable, launch=launch)

    outcome = run_runnable(
        workspace=workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled" or is_canceled():
        return started.stop("canceled", f"{step.subject} was canceled")

    return ReviewRun(
        ree_layout=layout,
        review_layout=review_layout,
        workspace=workspace,
        step=started,
        timer=timer,
        certified=certified,
        runnable=runnable,
        label=label,
        outcome=outcome,
        launch_script_digest=launch_digest(ree, launch),
    )
