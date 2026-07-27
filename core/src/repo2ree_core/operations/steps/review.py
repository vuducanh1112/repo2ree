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
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
from repo2ree_core.evidence.review.models import (
    EvidenceBasis,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
    attempt_basis,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import read_review_record, write_review_record
from repo2ree_core.ree.layout import ARTIFACTS_DIRNAME, ReviewLayout
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

# Signature of the per-handler early exit: a terminal status and why.
ReviewHalt = Callable[[ReviewStatus, str], ActionResult]


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
) -> tuple[ReviewRecord, ReviewHalt]:
    """Mark a step running on the persisted record and arm its halt.

    Every review step opens the same way: settle the step to ``running`` on disk
    *before* doing any work — so an attempt killed mid-step reads as a step that
    started rather than one that never ran — and build the halt that every
    non-success path below returns through (see :func:`review_step_halt`).

    Returns the started record, which is the one every later write must build on:
    the halt closes over it, so a handler that kept the pre-start record would
    persist a step whose status contradicts what the halt already wrote.
    """
    started = with_step(record, step, status="running", at=timer.started_at)
    write_review_record(review_layout, started)
    halt = review_step_halt(
        review_layout=review_layout,
        record=started,
        step=step,
        review_id=review_id,
        timer=timer,
        log=log,
        noun=noun,
    )
    return started, halt


def review_step_halt(
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
    complete with a verdict rather than halting here. Routing them through this
    would put the attempt into ``failed`` and conflate "the review could not
    run" with "the review has news".
    """

    def halt(status: ReviewStatus, message: str) -> ActionResult:
        timing = timer.finish()
        write_review_record(
            review_layout,
            with_step(record, step, status=status, at=timing.finished_at, failure=message),
        )
        log("system", "warn" if status == "canceled" else "error", f"{noun} {status}: {message}")
        if status == "canceled":
            return ActionResult(status="canceled", outputs={"review_id": review_id})
        return ActionResult.failed("precondition", message)

    return halt


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
