from __future__ import annotations

import platform
from collections.abc import Collection
from typing import TypedDict, get_args

from repo2ree_core.time_utils import OperationTiming
from repo2ree_protocol.command import ReviewBasis
from repo2ree_ree.model import Ree
from repo2ree_ree.primitives import RunId, UtcInstant
from repo2ree_ree.review import (
    EvidenceBasis,
    ExperimentComparison,
    ReviewExecutionStatus,
    ReviewLaunch,
    ReviewMachine,
    ReviewRecord,
    ReviewRunExperimentReceipt,
    ReviewStatus,
    ReviewStepKey,
    ReviewStepState,
    ReviewSubject,
)

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


def new_review_record(
    review_id: str,
    *,
    subject: ReviewSubject,
    at: UtcInstant,
    launch: ReviewLaunch | None = None,
) -> ReviewRecord:
    return ReviewRecord(
        review_id=review_id,
        subject=subject,
        machine=ReviewMachine(system=platform.system(), architecture=platform.machine()),
        created_at=at,
        updated_at=at,
        status="running",
        launch=launch or ReviewLaunch(),
    )


def review_subject(ree: Ree) -> ReviewSubject:
    definition = ree.subject.definition
    return ReviewSubject(
        name=definition.name,
        version=definition.catalog.version,
        ree_digest=ree.seal.ree_digest if ree.seal else None,
        experiments=tuple(experiment.name for experiment in definition.experiments),
    )


def with_step(
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    status: ReviewStatus,
    at: UtcInstant,
    failure: str | None = None,
) -> ReviewRecord:
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
    receipt: ReviewRunExperimentReceipt,
    comparison: ExperimentComparison,
) -> ReviewRecord:
    name = comparison.experiment_name
    receipts = [other for other in record.receipts.experiments if other.experiment_name != name] + [receipt]
    comparisons = [other for other in record.experiment_comparisons if other.experiment_name != name] + [comparison]
    receipts.sort(key=lambda entry: entry.experiment_name)
    comparisons.sort(key=lambda entry: entry.experiment_name)
    return record.model_copy(
        update={
            "receipts": record.receipts.model_copy(update={"experiments": receipts}),
            "experiment_comparisons": comparisons,
        }
    )


def experiment_comparison(record: ReviewRecord, experiment_name: str) -> ExperimentComparison | None:
    for comparison in record.experiment_comparisons:
        if comparison.experiment_name == experiment_name:
            return comparison
    return None


def resolve_basis(requested: ReviewBasis, *, available: Collection[EvidenceBasis]) -> EvidenceBasis | None:
    if requested != "auto":
        return requested if requested in available else None
    if "independent" in available:
        return "independent"
    return "bundled" if "bundled" in available else None


def attempt_basis(record: ReviewRecord) -> EvidenceBasis | None:
    settled = [
        comparison.basis
        for comparison in (record.source_comparison, record.experiment_environment_comparison)
        if comparison is not None
    ]
    if not settled:
        return None
    return "bundled" if "bundled" in settled else "independent"


def step_state(record: ReviewRecord, step: ReviewStepKey) -> ReviewStepState | None:
    for state in record.steps:
        if state.step == step:
            return state
    return None


def derive_attempt_status(steps: list[ReviewStepState]) -> ReviewStatus:
    present = {state.status for state in steps}
    for status in _STATUS_PRECEDENCE:
        if status in present:
            return status
    return "running"


def _latest_failure(steps: list[ReviewStepState]) -> str | None:
    unsuccessful = [state for state in steps if state.failure]
    if not unsuccessful:
        return None
    return max(unsuccessful, key=lambda state: state.updated_at).failure


def _step_order(state: ReviewStepState) -> int:
    return get_args(ReviewStepKey).index(state.step)
