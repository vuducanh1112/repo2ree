"""Machinery shared by the reviewer-side step handlers.

Everything here exists because a review step is structurally unlike an author
step: it writes into a parallel REE tree it must never escape, and every way it
can stop has to leave that tree's record consistent with what actually
happened. Two handlers could each spell that out; three cannot without the
copies drifting apart, which for this module means an attempt whose ``status``
disagrees with its own steps.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath

from repo2ree_core.reviews import (
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
    with_step,
    write_review_record,
)
from repo2ree_core.storage.layout import ARTIFACTS_DIRNAME, ReviewLayout
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

# Signature of the per-handler early exit: a terminal status and why.
ReviewHalt = Callable[[ReviewStatus, str], ActionResult]


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
