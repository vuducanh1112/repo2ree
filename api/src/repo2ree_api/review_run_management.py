from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import HTTPException

from repo2ree_api.run_registry import RunRegistry
from repo2ree_api.storage.review_files import review_metadata_path


# ================================================
# Types
# ================================================


ReviewRunOperation = Literal["build", "activation", "source"]


# ================================================
# Registry
# ================================================


def _require_review(review_id: str) -> None:
    if not review_metadata_path(review_id).exists():
        raise HTTPException(status_code=404, detail="Review not found")


_registry = RunRegistry("reviewId", _require_review, include_id_in_summary=False)

_append_review_run_log = _registry.append_log
_is_cancel_requested = _registry.is_cancel_requested
_mark_review_cancel_requested = _registry.mark_cancel_requested
_review_run_summary = _registry.run_summary
_get_review_run_state = _registry.get_run_state


def _start_background_review_run(
    review_id: str,
    operation: ReviewRunOperation,
    request_payload: dict[str, Any],
    run_id_prefix: str,
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    return _registry.start_background(
        review_id, operation, request_payload, run_id_prefix, runner
    )
