from __future__ import annotations

from contextlib import suppress

from repo2ree_core.persistence.files import json_document_bytes, write_atomic, write_json_atomic
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_ree.reserved_paths import experiment_slug
from repo2ree_ree.review import (
    ActivationOutcome,
    ExperimentComparison,
    ExperimentEnvironmentComparison,
    ReviewAcquireSourceReceipt,
    ReviewActivateExperimentEnvironmentReceipt,
    ReviewBuildExperimentEnvironmentReceipt,
    ReviewRecord,
    ReviewRunExperimentReceipt,
    ReviewSet,
    ReviewStepKey,
    SourceComparison,
)


def write_review_record(layout: ReviewLayout, record: ReviewRecord) -> None:
    write_json_atomic(layout.metadata, record.model_dump(mode="json"))


def read_review_record(layout: ReviewLayout) -> ReviewRecord | None:
    with suppress(Exception):
        return ReviewRecord.model_validate_json(layout.metadata.read_text(encoding="utf-8"))
    return None


def write_review_source_evidence(
    layout: ReviewLayout,
    receipt: ReviewAcquireSourceReceipt,
    comparison: SourceComparison,
) -> None:
    _write_review_evidence(layout, receipt, "acquire_source", comparison.model_dump(mode="json"))


def write_review_build_evidence(
    layout: ReviewLayout,
    receipt: ReviewBuildExperimentEnvironmentReceipt,
    comparison: ExperimentEnvironmentComparison,
) -> None:
    _write_review_evidence(layout, receipt, "build_experiment_environment", comparison.model_dump(mode="json"))


def write_review_activate_experiment_environment_evidence(
    layout: ReviewLayout,
    receipt: ReviewActivateExperimentEnvironmentReceipt,
    outcome: ActivationOutcome,
) -> None:
    _write_review_evidence(layout, receipt, "activate_experiment_environment", outcome.model_dump(mode="json"))


def write_review_experiment_evidence(
    layout: ReviewLayout,
    receipt: ReviewRunExperimentReceipt,
    comparison: ExperimentComparison,
) -> None:
    slug = experiment_slug(receipt.experiment_name)
    payload = json_document_bytes(receipt.model_dump(mode="json"))
    write_atomic(layout.run_receipt(receipt.run_id), payload)
    write_atomic(layout.experiment_receipt(slug), payload)
    write_json_atomic(layout.experiment_comparison(slug), comparison.model_dump(mode="json"))


def _write_review_evidence(
    layout: ReviewLayout,
    receipt: ReviewAcquireSourceReceipt
    | ReviewBuildExperimentEnvironmentReceipt
    | ReviewActivateExperimentEnvironmentReceipt,
    step: ReviewStepKey,
    comparison: dict[str, object],
) -> None:
    payload = json_document_bytes(receipt.model_dump(mode="json"))
    write_atomic(layout.run_receipt(receipt.run_id), payload)
    write_atomic(layout.operation_receipt(receipt.operation), payload)
    write_json_atomic(layout.comparison(step), comparison)


def load_reviews(layout: ReeLayout) -> ReviewSet:
    records: list[ReviewRecord] = []
    if not layout.reviews.is_dir():
        return ReviewSet()
    for path in layout.reviews.glob("*/review.json"):
        with suppress(Exception):
            records.append(ReviewRecord.model_validate_json(path.read_text(encoding="utf-8")))
    records.sort(key=lambda record: (record.created_at, record.review_id), reverse=True)
    return ReviewSet(reviews=records)
