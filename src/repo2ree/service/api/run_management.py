from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException

from repo2ree.service.storage.workspace_files import workspace_exists


RunOperation = Literal["build", "sbom", "activation", "source", "evaluate"]


_RUN_STORE: dict[str, dict[str, dict[str, Any]]] = {}
_RUN_CONTROL: dict[str, dict[str, dict[str, Any]]] = {}
_STORE_LOCK = RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_workspace(workspace_id: str) -> None:
    if not workspace_exists(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")


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
    workspace_id: str,
    run_id: str,
    operation: RunOperation,
    created_at: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    run_state = {
        "runId": run_id,
        "workspaceId": workspace_id,
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
    with _STORE_LOCK:
        _RUN_STORE.setdefault(workspace_id, {})[run_id] = run_state
        _RUN_CONTROL.setdefault(workspace_id, {})[run_id] = {
            "cancelRequested": False,
            "thread": None,
            "operation": operation,
        }
    return run_state


def _update_run_outputs(
    workspace_id: str, run_id: str, outputs: dict[str, Any]
) -> None:
    with _STORE_LOCK:
        run_state = _RUN_STORE.get(workspace_id, {}).get(run_id)
        if not run_state:
            return
        run_state["outputs"] = outputs


def _append_run_log(
    workspace_id: str,
    run_id: str,
    stream: str,
    level: str,
    message: str,
) -> None:
    with _STORE_LOCK:
        run_state = _RUN_STORE.get(workspace_id, {}).get(run_id)
        if not run_state:
            return
        next_seq = int(run_state.get("_nextSeq", 1))
        logs = run_state.setdefault("logs", [])
        next_seq = _append_log(logs, next_seq, stream, level, message)
        run_state["_nextSeq"] = next_seq


def _set_run_status(workspace_id: str, run_id: str, status: str) -> None:
    with _STORE_LOCK:
        run_state = _RUN_STORE.get(workspace_id, {}).get(run_id)
        if not run_state:
            return
        run_state["status"] = status
        if status in {"succeeded", "failed", "canceled"}:
            run_state["finishedAt"] = _utc_now()


def _mark_cancel_requested(workspace_id: str, run_id: str) -> bool:
    with _STORE_LOCK:
        control = _RUN_CONTROL.get(workspace_id, {}).get(run_id)
        run_state = _RUN_STORE.get(workspace_id, {}).get(run_id)
        if not control or not run_state:
            return False
        control["cancelRequested"] = True
        if run_state.get("status") in {"running", "queued", "created", "provisioning"}:
            run_state["status"] = "canceling"
        return True


def _is_cancel_requested(workspace_id: str, run_id: str) -> bool:
    with _STORE_LOCK:
        control = _RUN_CONTROL.get(workspace_id, {}).get(run_id)
        if not control:
            return False
        return bool(control.get("cancelRequested"))


def _set_run_thread(workspace_id: str, run_id: str, thread: Thread) -> None:
    with _STORE_LOCK:
        control = _RUN_CONTROL.get(workspace_id, {}).get(run_id)
        if control is not None:
            control["thread"] = thread


def _finalize_run(
    workspace_id: str,
    run_id: str,
    status: str,
    outputs: dict[str, Any],
) -> None:
    if _is_cancel_requested(workspace_id, run_id) and status not in {
        "failed",
        "succeeded",
    }:
        status = "canceled"
    _update_run_outputs(workspace_id, run_id, outputs)
    _set_run_status(workspace_id, run_id, status)
    with _STORE_LOCK:
        run_state = _RUN_STORE.get(workspace_id, {}).get(run_id)
        if run_state and "_nextSeq" in run_state:
            run_state.pop("_nextSeq", None)


def _start_background_run(
    workspace_id: str,
    operation: RunOperation,
    request_payload: dict[str, Any],
    run_id_prefix: str,
    runner: Callable[[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    _require_workspace(workspace_id)
    created_at = _utc_now()
    run_id = f"{run_id_prefix}-{uuid4().hex}"
    run_state = _create_run_state(
        workspace_id=workspace_id,
        run_id=run_id,
        operation=operation,
        created_at=created_at,
        request_payload=request_payload,
    )

    def _worker() -> None:
        try:
            status, outputs = runner(workspace_id, run_id)
        except HTTPException as exc:
            _append_run_log(
                workspace_id,
                run_id,
                "system",
                "error",
                str(exc.detail or "Run failed"),
            )
            status = (
                "canceled" if _is_cancel_requested(workspace_id, run_id) else "failed"
            )
            outputs = {}
        except Exception as exc:
            _append_run_log(workspace_id, run_id, "system", "error", str(exc))
            status = (
                "canceled" if _is_cancel_requested(workspace_id, run_id) else "failed"
            )
            outputs = {}
        _finalize_run(workspace_id, run_id, status, outputs)

    worker = Thread(target=_worker, daemon=True)
    _set_run_thread(workspace_id, run_id, worker)
    worker.start()
    return run_state


def _run_summary(run_state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run_state[key]
        for key in (
            "runId",
            "workspaceId",
            "operation",
            "status",
            "createdAt",
            "startedAt",
            "finishedAt",
            "outputs",
        )
    }


def _get_run_state(workspace_id: str, run_id: str) -> dict[str, Any]:
    _require_workspace(workspace_id)
    with _STORE_LOCK:
        workspace_runs = _RUN_STORE.get(workspace_id, {})
        run_state = workspace_runs.get(run_id)
    if not run_state:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_state


def _list_run_states(workspace_id: str) -> list[dict[str, Any]]:
    _require_workspace(workspace_id)
    with _STORE_LOCK:
        return list(_RUN_STORE.get(workspace_id, {}).values())


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
