"""The reviewer's evidence record: what an attempt is and what it holds.

A *review attempt* is one independent reproduction of an author's REE, kept in
its own namespace so it can never write to author evidence. It advances through
the reviewer-facing lifecycle — source, build, activation, experiments — one
step at a time, and each step contributes two things: a receipt (what the
reviewer's machine did) and a verdict (what that settles). The attempt's own
``status`` is derived from its steps; it is never set directly, so "the attempt
failed" can never disagree with "which step failed".

A step that ran to completion and found something unwelcome is ``completed``
with an unwelcome verdict, never ``failed`` — "the review could not run" and
"the review has news" must stay distinguishable.

Schemas plus the pure record algebra over them. How a verdict is *reached* is
``comparison``; where the record lives is ``store``.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import TypedDict

from repo2ree_core.time_utils import OperationTiming
from repo2ree_protocol.command import ReviewBasis
from repo2ree_ree.primitives import RunId, UtcInstant
from repo2ree_ree.review import (
    EvidenceBasis,
    ExperimentComparison,
    ReviewExecutionStatus,
    ReviewExperimentReceipt,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
    ReviewStepState,
)

# Attempt status resolution, most urgent first: a running step outranks a
# failure (the attempt is still moving), and any failure outranks a success.
_STATUS_PRECEDENCE: tuple[ReviewStatus, ...] = ("running", "failed", "canceled", "completed")


class ReviewReceiptEnvelopeFields(TypedDict):
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int
    recorded_at: UtcInstant
    status: ReviewExecutionStatus


def review_receipt_envelope(
    run_id: str,
    timing: OperationTiming,
    status: ReviewExecutionStatus,
) -> ReviewReceiptEnvelopeFields:
    return ReviewReceiptEnvelopeFields(
        run_id=RunId(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status=status,
    )


# ================================================
# Record Transitions
# ================================================


def new_review_record(review_id: str, *, at: str) -> ReviewRecord:
    """A fresh attempt with no steps taken yet."""
    return ReviewRecord(review_id=review_id, created_at=at, updated_at=at, status="running")


def with_step(
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    status: ReviewStatus,
    at: str,
    failure: str | None = None,
) -> ReviewRecord:
    """The record with one step's state written and the attempt re-derived.

    Re-running a step replaces its previous state: an attempt records where its
    lifecycle *stands*, while the per-run history stays in the review's
    ``runs/`` directory.
    """
    existing = step_state(record, step)
    state = ReviewStepState(
        step=step,
        status=status,
        started_at=at if existing is None or status == "running" else existing.started_at,
        updated_at=at,
        failure=failure,
    )
    steps = [other for other in record.steps if other.step != step] + [state]
    steps.sort(key=_step_order)
    return record.model_copy(
        update={
            "steps": steps,
            "updated_at": at,
            "status": derive_attempt_status(steps),
            "failure": _latest_failure(steps),
        }
    )


def with_experiment(
    record: ReviewRecord,
    receipt: ReviewExperimentReceipt,
    comparison: ExperimentComparison,
) -> ReviewRecord:
    """The record with one experiment's evidence written, replacing any prior run.

    Keyed by experiment name for the same reason :func:`with_step` is keyed by
    step: the attempt records where each part of its lifecycle *stands*, and the
    per-run history lives in ``runs/``. Re-running one experiment must not
    disturb the verdicts of its siblings, which is the whole reason this is a
    keyed replace rather than an append.
    """
    name = comparison.experiment_name
    receipts = [other for other in record.experiment_receipts if other.experiment_name != name] + [receipt]
    comparisons = [other for other in record.experiment_comparisons if other.experiment_name != name] + [comparison]
    receipts.sort(key=lambda entry: entry.experiment_name)
    comparisons.sort(key=lambda entry: entry.experiment_name)
    return record.model_copy(update={"experiment_receipts": receipts, "experiment_comparisons": comparisons})


def experiment_comparison(record: ReviewRecord, experiment_name: str) -> ExperimentComparison | None:
    """This attempt's verdict for one experiment, or None when it has not run."""
    for comparison in record.experiment_comparisons:
        if comparison.experiment_name == experiment_name:
            return comparison
    return None


def resolve_basis(requested: ReviewBasis, *, available: Collection[EvidenceBasis]) -> EvidenceBasis | None:
    """Settle a reviewer's requested basis against what a step can actually offer.

    Every step that takes a basis asks this same question, and the answer has to
    be the same one twice over. ``auto`` prefers the independent path and falls
    back, so a reviewer who states no preference always gets the strongest
    evidence on offer. An explicit request is never silently downgraded — handing
    back an integrity check to someone who asked for a reproduction is the one
    failure a review cannot afford — so it returns ``None`` instead, and the
    caller says why in the vocabulary of its own step.

    Only *what is on offer* differs between steps (an acquirable origin and a
    snapshot for source; a runnable recipe and a shipped artifact for the
    runtime), which is why that is the parameter and the rule above is not.
    """
    if requested != "auto":
        return requested if requested in available else None
    if "independent" in available:
        return "independent"
    return "bundled" if "bundled" in available else None


def attempt_basis(record: ReviewRecord) -> EvidenceBasis | None:
    """What this attempt's evidence as a whole is worth: its weakest link.

    A step that derives nothing from the outside world itself — activation runs
    the author's script in a workspace it did not assemble — has no basis of its
    own to report. It inherits this one, and inheriting the *weakest* settled
    basis is the only safe rule: an attempt that fetched the origin but then
    certified the runtime the bundle ships has not independently reproduced
    anything downstream of that runtime, whatever the source verdict says.

    ``None`` when nothing has settled yet, which is a precondition failure for
    any step that would have to inherit it rather than a basis to assume.
    """
    settled = [
        comparison.basis for comparison in (record.source_comparison, record.build_comparison) if comparison is not None
    ]
    if not settled:
        return None
    return "bundled" if "bundled" in settled else "independent"


def step_state(record: ReviewRecord, step: ReviewStepKey) -> ReviewStepState | None:
    """The recorded state of one step, or None when it has not been run."""
    for state in record.steps:
        if state.step == step:
            return state
    return None


def derive_attempt_status(steps: list[ReviewStepState]) -> ReviewStatus:
    """The attempt's status, as implied by the steps it has taken."""
    present = {state.status for state in steps}
    for status in _STATUS_PRECEDENCE:
        if status in present:
            return status
    return "running"


def _latest_failure(steps: list[ReviewStepState]) -> str | None:
    """The message of the most recently updated unsuccessful step."""
    unsuccessful = [state for state in steps if state.failure]
    if not unsuccessful:
        return None
    return max(unsuccessful, key=lambda state: state.updated_at).failure


def _step_order(state: ReviewStepState) -> int:
    """Lifecycle order, so a persisted record always reads front to back."""
    order: list[ReviewStepKey] = ["source", "build", "activation", "experiments"]
    return order.index(state.step)
