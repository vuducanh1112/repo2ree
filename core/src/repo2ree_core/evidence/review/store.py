"""Where a review attempt's record and per-step evidence live on disk.

Every attempt owns a namespace under the REE's ``reviews/`` directory, which is
what keeps a reviewer's evidence from ever landing in the author's: the two sets
are never written by the same paths.

Imperative shell: every function here touches the filesystem.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from repo2ree_core.evidence.receipts.models import (
    AcquireSourceReceipt,
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    RunExperimentReceipt,
)
from repo2ree_core.evidence.review.models import (
    ActivationOutcome,
    BuildComparison,
    ExperimentComparison,
    ReviewRecord,
    ReviewSet,
    ReviewStepKey,
    SourceComparison,
)
from repo2ree_core.ree.layout import ReeLayout, ReviewLayout
from repo2ree_core.reserved_paths import experiment_slug


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


def write_review_activation_evidence(
    layout: ReviewLayout,
    receipt: ActivationTestReceipt,
    outcome: ActivationOutcome,
) -> None:
    """Persist the activation probe beside the other steps' evidence.

    Filed under ``comparisons/activation.json`` despite not being a comparison:
    the directory is the attempt's per-step verdict store, and giving activation
    its own would split one lookup into two for a distinction the reader already
    gets from the document's ``policy``.
    """
    _write_review_evidence(layout, receipt, "activation", outcome.model_dump(mode="json"))


def write_review_experiment_evidence(
    layout: ReviewLayout,
    receipt: RunExperimentReceipt,
    comparison: ExperimentComparison,
) -> None:
    """Persist one experiment's evidence under its own slug.

    Unlike the other three steps, the per-operation slot cannot be
    ``receipts/run_experiment.json``: every experiment shares that operation, so
    a second one would overwrite the first's receipt and the attempt would end
    up holding one experiment's evidence for all of them. The author side hit
    this first and answered it by keying experiments under a slug directory
    (:func:`repo2ree_core.evidence.receipts.store.author_receipt_path`); this mirrors that so
    both sides of the same REE are laid out the same way.
    """
    slug = experiment_slug(receipt.experiment_name)
    payload = receipt.model_dump(mode="json")
    _atomic_write_json(layout.run_receipt(receipt.run_id), payload)
    _atomic_write_json(layout.experiment_receipt(slug), payload)
    _atomic_write_json(layout.experiment_comparison(slug), comparison.model_dump(mode="json"))


def _write_review_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt | BuildRuntimeReceipt | ActivationTestReceipt,
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
