"""Machinery shared by the reviewer-side step handlers.

Everything here exists because a review step is structurally unlike an author
step: it writes into a parallel REE tree it must never escape, and every way it
can stop has to leave that tree's record consistent with what actually
happened. Two handlers could each spell that out; three cannot without the
copies drifting apart, which for this module means an attempt whose ``status``
disagrees with its own steps.

The same argument runs through :func:`require_certified_runtime`, and there it
is about the verdict rather than the record: every step that runs *inside* what
the build left behind must first prove that what is there is still what was
certified. A copy of that check that drifted would leave a pass standing over a
runtime nobody can point to — which is worse than no verdict, because it still
reads as one.

A step ends exactly two ways, and both are owned here: :class:`ReviewStep`
hands a handler its ``stop`` and its ``settle`` together, so the record, the log
line, and the span agree however the step came out. They are one object because
they are one obligation — a settle that spelled the closing line itself would
be a fifth copy of the format string the halt already owns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
from repo2ree_core.evidence.review.models import (
    ActivationVerdict,
    BuildVerdict,
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentVerdict,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
    attempt_basis,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import read_review_record, write_review_record
from repo2ree_core.execution.experiment.resolve import RunnableResolutionError
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.ree.layout import ARTIFACTS_DIRNAME, ReeLayout, ReviewLayout
from repo2ree_core.ree.store import UNREADABLE_DOCUMENT, ReeStore
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import ReviewStepAttrs

# Signature of the per-handler early exit: a terminal status and why.
ReviewHalt = Callable[[ReviewStatus, str], ActionResult]

# What a completed step settled. Each step draws from its own vocabulary — the
# four are disjoint apart from ``identical``, which means the same thing in all
# of them — and the union is what the shared exit accepts, so a step cannot
# report a verdict from a lifecycle it does not belong to.
ReviewVerdict = ComparisonVerdict | BuildVerdict | ActivationVerdict | ExperimentVerdict


class ReviewSettle(Protocol):
    """Signature of the per-handler success exit.

    Spelled as a protocol rather than a ``Callable[...]`` alias so the keyword
    arguments stay checked: what a step settled is optional (a source step has
    no runtime to name) and a typo in one of them would otherwise be accepted
    and silently dropped from the span.
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

    ``record`` is the *started* record — the one every later write must build
    on, since ``stop`` and ``settle`` both close over it. A handler that kept
    the pre-start record would persist a step whose status contradicts what the
    exit already wrote.

    ``stop`` and ``settle`` are plain callables held as fields rather than
    methods, because they are closures over the step's identity (layout, key,
    timer, log, noun) that a handler should not be able to call with a
    different one.
    """

    record: ReviewRecord
    stop: ReviewHalt
    settle: ReviewSettle


def require_ree_intent(ree_layout: ReeLayout, *, log: LogSink) -> ReeIntent | ActionResult:
    """The author baseline this attempt reviews, or the failure to return.

    Every review step reads the intent — for the origin to fetch, the runtime to
    certify, the runnable to run — and none of them can do anything without it.
    Read *before* the step is marked running, for the same reason
    :func:`require_review_record` is: a baseline nobody can read is a
    precondition nobody can meet, so there is nothing to mark running and
    nothing to settle a halt on.

    Unguarded, this was where a review command against an uninitialised or
    damaged workbench raised straight out of the handler — past the dispatcher,
    which does not catch, and out of the executor as a traceback with no
    ``ActionResult`` at all, which is not a shape the callers upstream have any
    way to read. Callers ``return`` the ActionResult unchanged::

        intent = require_ree_intent(ree_layout, log=log)
        if isinstance(intent, ActionResult):
            return intent
    """
    store = ReeStore(ree_layout)
    if not store.metadata_exists():
        message = "This workbench holds no REE to review"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)
    try:
        return store.read_intent()
    except UNREADABLE_DOCUMENT as exc:
        # A precondition rather than an `internal` fault: the document is the
        # REE's, not this code's, and a reviewer's next action is to fix the
        # baseline rather than to report a bug.
        message = f"The REE under review has unreadable metadata: {exc}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)


def require_review_record(review_layout: ReviewLayout, review_id: str, log: LogSink) -> ReviewRecord | ActionResult:
    """The attempt this step joins, or the failure to return when there is none.

    Only the source step opens an attempt; every later step joins one the source
    step already created, so "no such attempt" is the same precondition failure
    for all of them. Note that it halts *before* :func:`begin_review_step` — with
    no record there is nothing to mark running and nothing to record a halt on.
    Callers ``return`` the ActionResult unchanged::

        record = require_review_record(review_layout, args.review_id, log)
        if isinstance(record, ActionResult):
            return record
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

    Every review step opens the same way: settle the step to ``running`` on disk
    *before* doing any work — so an attempt killed mid-step reads as a step that
    started rather than one that never ran — and build the two exits below that
    every path out of the handler returns through.

    The step's identity goes on the command span here rather than at either
    exit, so a step killed mid-run is still attributable to its attempt.
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
    """Build the "stop here and record why" exit for one review step.

    Every non-success path a review step can take — canceled, a precondition it
    cannot meet, a script that exited nonzero — has to do the same three things
    in the same order: settle the step on the persisted record, say so in the
    log, and return a result that agrees with both. Handlers call the returned
    function and ``return`` its value unchanged.

    Note what this is *not* for: a step that ran to completion and found
    something unwelcome. A build whose closure differs and an activation whose
    runtime would not come up are both the review working correctly, and they
    complete through :func:`_review_step_settle` with a verdict rather than
    halting here. Routing them through this would put the attempt into
    ``failed`` and conflate "the review could not run" with "the review has
    news".
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

    The counterpart of :func:`_review_step_halt`, and the reviewer-side
    counterpart of :func:`~repo2ree_core.operations.steps.author.settle_step` —
    the same "settle the record and report consistently" job for a lifecycle
    whose record is a persisted attempt rather than a receipt.

    ``completed`` whatever the verdict, because the verdict is not this
    function's business: a build whose closure differs and a runtime that would
    not come up are both steps that did their job. Only the halt above records
    a step that could not run.

    The handler passes the record already carrying this step's evidence (the
    receipt and the comparison it just wrote), together with the ``timing`` that
    evidence was stamped with — the same reading, so the record can never claim
    a duration its own receipt contradicts. What it settled goes on the span
    here, which is the one place that sees every step's verdict.
    """

    def settle(
        record: ReviewRecord,
        timing: OperationTiming,
        *,
        verdict: ReviewVerdict | None = None,
        basis: EvidenceBasis | None = None,
        runtime_digest: str | None = None,
    ) -> None:
        write_review_record(review_layout, with_step(record, step, status="completed", at=timing.finished_at))
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

    The review lifecycle is a chain — source, build, activation, experiments —
    and each link is worth nothing without the one before it. ``message`` says
    what to do about it rather than restating the graph, because a client that
    called out of order needs the next action, not the topology. Callers::

        halted = require_completed_step(started, "build", stop=stop, message="…")
        if halted is not None:
            return halted
    """
    state = step_state(record, step)
    if state is None or state.status != "completed":
        return stop("failed", message)
    return None


@dataclass(frozen=True)
class CertifiedRuntime:
    """The runtime a review attempt certified, confirmed still to be that one.

    ``runtime_path`` is empty for a baseline that declares no runtime artifact —
    a native experiment — in which case ``runtime_digest`` is None and there is
    nothing to bind. Steps that cannot run without a runtime say so themselves;
    this value reports what the attempt has, not what a caller needs.
    """

    basis: EvidenceBasis
    build_receipt: BuildRuntimeReceipt
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

    Three things have to hold before any step can run *inside* what the build
    left behind, and they are the same three whichever step is asking: the
    attempt settled a basis and a build receipt, its workspace is still there,
    and the runtime sitting in that workspace is byte-for-byte the one the build
    certified. That last check is why this is shared rather than repeated — a
    re-run build would otherwise leave an earlier step's verdict standing over a
    runtime that no longer exists, and a verdict about bytes nobody can point to
    is worse than no verdict.

    ``purpose`` completes "This attempt has recorded no runtime …" and
    ``retry_purpose`` completes "… re-run the build review …", so each step says
    what *it* was trying to do. Callers ``return`` an ActionResult unchanged::

        certified = require_certified_runtime(started, review_layout, stop=stop, …)
        if isinstance(certified, ActionResult):
            return certified
    """
    basis = attempt_basis(record)
    if basis is None or record.build_receipt is None:
        return stop("failed", f"This attempt has recorded no runtime {purpose}")

    # The workspace is the whole apparatus here: the reviewer's source, the
    # author's recipe, and the runtime beside them. Reclaiming it is a supported
    # choice at build time, so hitting this is a reviewer's own doing and the
    # message says how to undo it rather than reporting a bare missing path.
    if not review_layout.workspace.is_dir():
        return stop(
            "failed",
            f"This attempt's workspace was reclaimed after the build; re-run the build review {retry_purpose}",
        )

    runtime_path = (record.build_receipt.runtime_path or "").strip()
    runtime_digest = digest_file_if_exists(workspace_runtime(review_layout, runtime_path)) if runtime_path else None
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


def workspace_runtime_candidates(review_layout: ReviewLayout, runtime_path: str) -> tuple[Path, ...]:
    """Where a runtime can sit in the reviewer's workspace, declared path first.

    Normally there is only one answer. The exception is a baseline loaded from a
    bundle: packaging lifted the runtime into ``artifacts/`` and rewrote the
    declared path to ``artifacts/<basename>``, discarding the workspace path the
    build script actually writes to. That remap keeps the basename by
    construction, so undoing it is a lookup rather than a guess — and without it
    a loaded REE could never be rebuilt at all, only certified against itself.
    """
    declared = review_layout.workspace / runtime_path
    parts = PurePosixPath(runtime_path).parts
    if len(parts) == 2 and parts[0] == ARTIFACTS_DIRNAME:
        return (declared, review_layout.workspace / parts[1])
    return (declared,)


def workspace_runtime(review_layout: ReviewLayout, runtime_path: str) -> Path:
    """The runtime in the reviewer's workspace, wherever it legitimately landed.

    Falls back to the declared path when none of the candidates exist, so a miss
    is reported against the path the author declared rather than against a
    fallback the author never named.
    """
    candidates = workspace_runtime_candidates(review_layout, runtime_path)
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


# ================================================
# Running one of the author's runnables
# ================================================


#: An extra precondition a step has that the others do not, checked once the
#: certified runtime is in hand. Returns the refusal message, or None to admit.
ReviewAdmission = Callable[[ReviewRecord, CertifiedRuntime], str | None]


@dataclass(frozen=True)
class ReviewRunnableStep[RunnableT: Runnable]:
    """What distinguishes the two review steps that run one of the author's runnables.

    The reviewer-side counterpart of
    :class:`~repo2ree_core.operations.steps.author.RunnableStep`, and it stops
    at the same place for the same reason. Activation and experiments *get to*
    their run identically — join the attempt, prove the step before them
    completed, prove the certified runtime is still the certified runtime,
    resolve the author's runnable, run it — and that is what this descriptor
    covers.

    What they do *afterwards* is not covered and deliberately stays in the
    handlers: they write different evidence documents, attach them to different
    fields of the record, and reach their verdicts by different rules (one
    compares nothing, the other diffs against the author's recorded run). A
    runner that owned settlement too would need a callback carrying most of
    each handler's body, which is a parameter list pretending to be an
    abstraction.

    ``admit`` is the one precondition that is genuinely per-step — activation
    needs a runtime artifact to probe, an experiment needs an activation that
    actually passed — and it runs after certification, so both steps report the
    apparatus being absent before reporting what they wanted it for.

    Generic in the runnable it selects so a handler gets back what it resolved
    rather than the widened base: an experiment step needs the ``name`` and
    ``output_paths`` only an :class:`~repo2ree_core.domain.experiment.Experiment`
    has, and narrowing that back with a runtime check would be this module's
    typing weakness paid for at every call site.
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
    #: :class:`RunnableResolutionError` when the baseline cannot produce it.
    select: Callable[[ReeIntent], tuple[RunnableT, str]]
    #: Completes "<unresolvable>: <why>" when ``select`` refuses.
    unresolvable: str
    #: Completes "the author baseline declares <script_noun> that is not there".
    script_noun: str


@dataclass(frozen=True)
class ReviewRun[RunnableT: Runnable]:
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
    runnable: RunnableT
    label: str
    outcome: ExperimentRunOutcome


def open_review_run[RunnableT: Runnable](
    step: ReviewRunnableStep[RunnableT],
    *,
    review_id: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ReviewRun[RunnableT] | ActionResult:
    """Take a review step from its command up to the end of its run.

    Returns the run for the handler to judge, or the ``ActionResult`` to return
    unchanged — every refusal below has already settled the attempt's record and
    said why, so a caller never has to decide how a halt is reported::

        opened = open_review_run(_ACTIVATION, review_id=args.review_id, …)
        if isinstance(opened, ActionResult):
            return opened
    """
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(review_id)
    timer = OperationTimer.start()

    intent = require_ree_intent(ree_layout, log=log)
    if isinstance(intent, ActionResult):
        return intent

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
        runnable, label = step.select(intent)
    except RunnableResolutionError as exc:
        return started.stop("failed", f"{step.unresolvable}: {exc}")

    # A script that is not there would otherwise run, fail, and be recorded as a
    # verdict about something nothing ever exercised. Absent apparatus is a fact
    # about the baseline, so it fails the step rather than settling a verdict.
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
