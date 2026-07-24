"""Persistent reviewer evidence sets and source-identity comparisons."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.receipts import AcquireSourceReceipt
from repo2ree_core.storage.layout import ReeLayout, ReviewLayout

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ComparisonVerdict = Literal["identical", "different", "inconclusive"]


class _ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceComparison(_ReviewModel):
    policy: Literal["swhid"] = "swhid"
    expected_swhid: str | None = None
    observed_swhid: str | None = None
    verdict: ComparisonVerdict


class ReviewRecord(_ReviewModel):
    review_id: str
    created_at: str
    updated_at: str
    status: ReviewStatus
    source_receipt: AcquireSourceReceipt | None = None
    source_comparison: SourceComparison | None = None
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)


def compare_source_swhids(expected: str, observed: str) -> SourceComparison:
    """Compare the author's source identity with a freshly acquired tree."""
    normalized_expected = expected.strip() or None
    normalized_observed = observed.strip() or None
    if normalized_expected is None or normalized_observed is None:
        verdict: ComparisonVerdict = "inconclusive"
    elif normalized_expected == normalized_observed:
        verdict = "identical"
    else:
        verdict = "different"
    return SourceComparison(
        expected_swhid=normalized_expected,
        observed_swhid=normalized_observed,
        verdict=verdict,
    )


def write_review_record(layout: ReviewLayout, record: ReviewRecord) -> None:
    _atomic_write_json(layout.metadata, record.model_dump(mode="json"))


def write_review_source_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt,
    comparison: SourceComparison,
) -> None:
    payload = receipt.model_dump(mode="json")
    _atomic_write_json(layout.run_receipt(receipt.run_id), payload)
    _atomic_write_json(layout.operation_receipt(receipt.operation), payload)
    _atomic_write_json(layout.comparison("source"), comparison.model_dump(mode="json"))


def load_reviews(layout: ReeLayout) -> ReviewSet:
    records: list[ReviewRecord] = []
    if not layout.reviews.is_dir():
        return ReviewSet()
    for path in layout.reviews.glob("*/review.json"):
        with suppress(Exception):
            records.append(ReviewRecord.model_validate_json(path.read_text(encoding="utf-8")))
    records.sort(key=lambda record: (record.created_at, record.review_id), reverse=True)
    return ReviewSet(reviews=records)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
