from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from repo2ree_api.storage.review_files import review_metadata_path


ReviewRunOperation = Literal["build", "activation", "source"]


_REVIEW_RUN_STORE: dict[str, dict[str, dict[str, Any]]] = {}
_REVIEW_RUN_CONTROL: dict[str, dict[str, dict[str, Any]]] = {}
_REVIEW_STORE_LOCK = RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_review(review_id: str) -> None:
    if not review_metadata_path(review_id).exists():
        raise HTTPException(status_code=404, detail="Review not found")


def _append_log(
    entries: list[dict[str, Any]],
    seq: int,
    stream: str,
    level: str,
    message: str,
) -> int:
    entries.append(
        {
            "seq": seq,
            "ts": _utc_now(),
            "stream": stream,
            "level": level,
            "message": message,
        }
    )
    return seq + 1


def _create_run_state(
    review_id: str,
    run_id: str,
    operation: ReviewRunOperation,
    created_at: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    run_state: dict[str, Any] = {
        "runId": run_id,
        "reviewId": review_id,
        "operation": operation,
        "status": "running",
        "createdAt": created_at,
        "startedAt": created_at,
        "finishedAt": None,
        "outputs": {},
        "logs": [],
        "request": request_payload,
        "_nextSeq": 1,
    }
    with _REVIEW_STORE_LOCK:
        _REVIEW_RUN_STORE.setdefault(review_id, {})[run_id] = run_state
        _REVIEW_RUN_CONTROL.setdefault(review_id, {})[run_id] = {
            "cancelRequested": False,
            "thread": None,
            "operation": operation,
        }
    return run_state


def _append_review_run_log(
    review_id: str,
    run_id: str,
    stream: str,
    level: str,
    message: str,
) -> None:
    with _REVIEW_STORE_LOCK:
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
        if not run_state:
            return
        next_seq = int(run_state.get("_nextSeq", 1))
        logs = run_state.setdefault("logs", [])
        next_seq = _append_log(logs, next_seq, stream, level, message)
        run_state["_nextSeq"] = next_seq


def _is_cancel_requested(review_id: str, run_id: str) -> bool:
    with _REVIEW_STORE_LOCK:
        control = _REVIEW_RUN_CONTROL.get(review_id, {}).get(run_id)
        if not control:
            return False
        return bool(control.get("cancelRequested"))


def _mark_review_cancel_requested(review_id: str, run_id: str) -> bool:
    with _REVIEW_STORE_LOCK:
        control = _REVIEW_RUN_CONTROL.get(review_id, {}).get(run_id)
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
        if not control or not run_state:
            return False
        control["cancelRequested"] = True
        if run_state.get("status") in {"running", "queued", "created", "provisioning"}:
            run_state["status"] = "canceling"
        return True


def _set_run_status(review_id: str, run_id: str, status: str) -> None:
    with _REVIEW_STORE_LOCK:
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
        if not run_state:
            return
        run_state["status"] = status
        if status in {"succeeded", "failed", "canceled"}:
            run_state["finishedAt"] = _utc_now()


def _finalize_run(
    review_id: str,
    run_id: str,
    status: str,
    outputs: dict[str, Any],
) -> None:
    if _is_cancel_requested(review_id, run_id) and status not in {
        "failed",
        "succeeded",
    }:
        status = "canceled"
    with _REVIEW_STORE_LOCK:
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
        if run_state:
            run_state["outputs"] = outputs
    _set_run_status(review_id, run_id, status)
    with _REVIEW_STORE_LOCK:
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
        if run_state and "_nextSeq" in run_state:
            run_state.pop("_nextSeq", None)


def _start_background_review_run(
    review_id: str,
    operation: ReviewRunOperation,
    request_payload: dict[str, Any],
    run_id_prefix: str,
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    _require_review(review_id)
    created_at = _utc_now()
    run_id = f"{run_id_prefix}-{uuid4().hex}"
    run_state = _create_run_state(
        review_id=review_id,
        run_id=run_id,
        operation=operation,
        created_at=created_at,
        request_payload=request_payload,
    )

    def _worker() -> None:
        try:
            status, outputs = runner(review_id, run_id)
        except HTTPException as exc:
            _append_review_run_log(
                review_id,
                run_id,
                "system",
                "error",
                str(exc.detail or "Run failed"),
            )
            status = "canceled" if _is_cancel_requested(review_id, run_id) else "failed"
            outputs = {}
        except Exception as exc:
            _append_review_run_log(review_id, run_id, "system", "error", str(exc))
            status = "canceled" if _is_cancel_requested(review_id, run_id) else "failed"
            outputs = {}
        _finalize_run(review_id, run_id, status, outputs)

    worker = Thread(target=_worker, daemon=True)
    with _REVIEW_STORE_LOCK:
        control = _REVIEW_RUN_CONTROL.get(review_id, {}).get(run_id)
        if control is not None:
            control["thread"] = worker
    worker.start()
    return run_state


def _review_run_summary(run_state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run_state[key]
        for key in (
            "runId",
            "operation",
            "status",
            "createdAt",
            "startedAt",
            "finishedAt",
            "outputs",
        )
    }


def _get_review_run_state(review_id: str, run_id: str) -> dict[str, Any]:
    _require_review(review_id)
    with _REVIEW_STORE_LOCK:
        run_state = _REVIEW_RUN_STORE.get(review_id, {}).get(run_id)
    if not run_state:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_state


def _paginate(
    items: list[dict[str, Any]], cursor: str | None, limit: int | None
) -> tuple[list[dict[str, Any]], str | None, bool]:
    start = 0
    if cursor:
        try:
            start = max(int(cursor), 0)
        except ValueError:
            start = 0
    end = len(items)
    if limit is not None and limit >= 0:
        end = min(start + limit, len(items))
    page = items[start:end]
    has_more = end < len(items)
    next_cursor = str(end) if has_more else None
    return page, next_cursor, has_more
