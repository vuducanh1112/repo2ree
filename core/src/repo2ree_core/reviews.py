"""Persistent reviewer evidence sets and the comparisons that certify them.

A *review attempt* is one independent reproduction of an author's REE, kept in
its own namespace so it can never write to author evidence. It advances through
the reviewer-facing lifecycle — source, build, activation, experiments — one
step at a time, and each step contributes two things: a receipt (what the
reviewer's machine did) and a comparison (how that compares to what the author
recorded). The attempt's own ``status`` is derived from its steps; it is never
set directly, so "the attempt failed" can never disagree with "which step
failed".

The comparison policy differs per step because the certifiable property does:

* source — SWHID identity, which *is* reproducible bit for bit;
* build — SBOM closure equivalence, because container builds are routinely not
  bit-reproducible even from identical inputs (see
  :mod:`repo2ree_core.sbom.equivalence`). A digest match is the stronger
  verdict where it happens, not the only acceptable one.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.receipts import AcquireSourceReceipt, BuildRuntimeReceipt
from repo2ree_core.sbom.cyclonedx import ObservedPackage
from repo2ree_core.sbom.equivalence import (
    PackageDelta,
    closure_verdict,
    compare_sbom_closures,
)
from repo2ree_core.storage.layout import ReeLayout, ReviewLayout

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ReviewStepKey = Literal["source", "build", "activation", "experiments"]
ComparisonVerdict = Literal["identical", "different", "inconclusive"]
BuildVerdict = Literal["identical", "equivalent", "different", "inconclusive"]

# Attempt status resolution, most urgent first: a running step outranks a
# failure (the attempt is still moving), and any failure outranks a success.
_STATUS_PRECEDENCE: tuple[ReviewStatus, ...] = ("running", "failed", "canceled", "completed")


class _ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ================================================
# Comparisons
# ================================================


class SourceComparison(_ReviewModel):
    policy: Literal["swhid"] = "swhid"
    expected_swhid: str | None = None
    observed_swhid: str | None = None
    verdict: ComparisonVerdict


class PackageDeltaRecord(_ReviewModel):
    """One package the author's and the reviewer's runtimes disagree about."""

    ecosystem: str
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


class BuildComparison(_ReviewModel):
    """How a reviewer's rebuilt runtime compares to the author's.

    Carries both tiers of evidence: the runtime digests (which settle
    ``identical`` when a build happens to be bit-reproducible) and the SBOM
    closure delta (which settles the rest). The listed deltas are capped
    samples — the ``*_count`` fields are the whole truth.
    """

    policy: Literal["sbom-closure"] = "sbom-closure"
    verdict: BuildVerdict
    # Runtime artifact tier.
    expected_runtime_digest: str | None = None
    observed_runtime_digest: str | None = None
    # Closure tier: which documents were compared, and by what.
    expected_sbom_digest: str | None = None
    observed_sbom_digest: str | None = None
    sbom_tool_version: str | None = None
    # Closure aggregates.
    expected_package_total: int = 0
    observed_package_total: int = 0
    matched: int = 0
    missing_count: int = 0
    extra_count: int = 0
    version_mismatch_count: int = 0
    advisory_count: int = 0
    # Capped samples.
    missing: list[PackageDeltaRecord] = Field(default_factory=list)
    extra: list[PackageDeltaRecord] = Field(default_factory=list)
    version_mismatches: list[PackageDeltaRecord] = Field(default_factory=list)
    advisory: list[PackageDeltaRecord] = Field(default_factory=list)


# ================================================
# Records
# ================================================


class ReviewStepState(_ReviewModel):
    """The lifecycle state of one step within a review attempt."""

    step: ReviewStepKey
    status: ReviewStatus
    started_at: str
    updated_at: str
    failure: str | None = None


class ReviewRecord(_ReviewModel):
    """One independent review attempt: its lifecycle plus its evidence.

    ``status`` and ``failure`` are derived from ``steps`` — write through
    :func:`with_step` rather than setting them.
    """

    review_id: str
    created_at: str
    updated_at: str
    status: ReviewStatus
    steps: list[ReviewStepState] = Field(default_factory=list)
    source_receipt: AcquireSourceReceipt | None = None
    source_comparison: SourceComparison | None = None
    build_receipt: BuildRuntimeReceipt | None = None
    build_comparison: BuildComparison | None = None
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)


# ================================================
# Comparison Construction
# ================================================


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


def compare_build_runtimes(
    *,
    expected_runtime_digest: str | None,
    observed_runtime_digest: str | None,
    expected_packages: list[ObservedPackage],
    observed_packages: list[ObservedPackage],
    expected_sbom_digest: str | None = None,
    observed_sbom_digest: str | None = None,
    sbom_tool_version: str | None = None,
) -> BuildComparison:
    """Certify a rebuilt runtime against the author's, digests first.

    The ladder, strongest first: equal runtime digests mean the build is bit
    reproducible (``identical``); otherwise the dependency closures decide
    (``equivalent`` / ``different``); a closure that cannot be compared at all
    — no author SBOM, or a scan that yielded nothing — is ``inconclusive``
    rather than a pass, because an absent baseline is not agreement.
    """
    delta = compare_sbom_closures(expected_packages, observed_packages)
    if expected_runtime_digest and expected_runtime_digest == observed_runtime_digest:
        verdict: BuildVerdict = "identical"
    else:
        verdict = closure_verdict(delta)
    return BuildComparison(
        verdict=verdict,
        expected_runtime_digest=expected_runtime_digest,
        observed_runtime_digest=observed_runtime_digest,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=observed_sbom_digest,
        sbom_tool_version=sbom_tool_version,
        expected_package_total=delta.expected_total,
        observed_package_total=delta.observed_total,
        matched=delta.matched,
        missing_count=delta.missing_count,
        extra_count=delta.extra_count,
        version_mismatch_count=delta.version_mismatch_count,
        advisory_count=delta.advisory_count,
        missing=_delta_records(delta.missing),
        extra=_delta_records(delta.extra),
        version_mismatches=_delta_records(delta.version_mismatches),
        advisory=_delta_records(delta.advisory),
    )


def _delta_records(deltas: list[PackageDelta]) -> list[PackageDeltaRecord]:
    return [
        PackageDeltaRecord(
            ecosystem=delta.ecosystem,
            name=delta.name,
            expected_version=delta.expected_version,
            observed_version=delta.observed_version,
        )
        for delta in deltas
    ]


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


# ================================================
# Persistence
# ================================================


def write_review_record(layout: ReviewLayout, record: ReviewRecord) -> None:
    _atomic_write_json(layout.metadata, record.model_dump(mode="json"))


def read_review_record(layout: ReviewLayout) -> ReviewRecord | None:
    """The persisted attempt, or None when this namespace holds no review."""
    with suppress(Exception):
        return ReviewRecord.model_validate_json(layout.metadata.read_text(encoding="utf-8"))
    return None


def write_review_source_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt,
    comparison: SourceComparison,
) -> None:
    _write_review_evidence(layout, receipt, "source", comparison.model_dump(mode="json"))


def write_review_build_evidence(
    layout: ReviewLayout,
    receipt: BuildRuntimeReceipt,
    comparison: BuildComparison,
) -> None:
    _write_review_evidence(layout, receipt, "build", comparison.model_dump(mode="json"))


def _write_review_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt | BuildRuntimeReceipt,
    step: ReviewStepKey,
    comparison: dict[str, object],
) -> None:
    """Persist one step's receipt twice (by run, by operation) and its comparison.

    The same selection rule the author side uses: ``runs/`` keeps the immutable
    history, ``receipts/<operation>.json`` keeps the latest per operation.
    """
    payload = receipt.model_dump(mode="json")
    _atomic_write_json(layout.run_receipt(receipt.run_id), payload)
    _atomic_write_json(layout.operation_receipt(receipt.operation), payload)
    _atomic_write_json(layout.comparison(step), comparison)


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
