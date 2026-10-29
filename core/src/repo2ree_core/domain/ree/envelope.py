from __future__ import annotations

from typing import TypedDict

from repo2ree_core.time_utils import OperationTiming
from repo2ree_ree.primitives import RunId, UtcInstant


class ReceiptEnvelopeFields(TypedDict):
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int
    recorded_at: UtcInstant


def receipt_envelope(run_id: str, timing: OperationTiming) -> ReceiptEnvelopeFields:
    """Construct the successful receipt envelope for a completed operation."""
    return ReceiptEnvelopeFields(
        run_id=RunId(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
    )
