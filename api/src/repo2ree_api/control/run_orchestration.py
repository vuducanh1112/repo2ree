from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from repo2ree_api.control.run_registry import RunRegistry
from repo2ree_api.deps import command_dispatcher, ree_registry
from repo2ree_api.settings import service_settings
from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_api.storage.run_store import StoredRun
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import ReeBusyError, ReeRoute
from repo2ree_telemetry.behaviour.events import AuthorApiActionName


def _require_ree(ree_id: str) -> None:
    require_handle(ree_id)


_registry = RunRegistry(
    _require_ree,
    JsonRunStore(service_settings.RUN_REGISTRY_DIR),
    max_workers=service_settings.RUN_MAX_WORKERS,
)

append_run_log = _registry.append_log
update_run_outputs = _registry.update_outputs
is_cancel_requested = _registry.is_cancel_requested
mark_cancel_requested = _registry.mark_cancel_requested
run_summary = _registry.run_summary
run_action_id = _registry.action_of
get_run_state = _registry.get_run_state
get_run_summary = _registry.get_run_summary
list_runs = _registry.list_runs
observe_run = _registry.observe
list_run_logs = _registry.list_run_logs
start_background_run = _registry.start_background
stop_runs = _registry.stop
shutdown_runs = _registry.shutdown


def startup_runs() -> None:
    _registry.startup(_resume)


def deliver_cancel(ree_id: str, run_id: str, handle: ReeRoute) -> None:
    run = _registry.get(ree_id, run_id)
    if run is None or run.cancel_requested_at is None or run.cancel_sent:
        return
    command_dispatcher.cancel_run(handle, run_id)
    _registry.mark_cancel_sent(ree_id, run_id)


def _following(ree_id: str, run_id: str) -> dict[str, Any]:
    def deferred_cancel(handle: ReeRoute) -> None:
        try:
            deliver_cancel(ree_id, run_id, handle)
        except Exception:  # noqa: BLE001
            append_run_log(ree_id, run_id, "system", "warn", "Cancellation signal could not reach the workbench")

    return {
        "on_started": lambda context: _registry.record_start(ree_id, run_id, context),
        "on_progress": lambda offset: _registry.record_progress(ree_id, run_id, offset),
        "on_session": deferred_cancel,
        "stop": _registry.stopping,
        "reconnect_timeout": None,
    }


def _resume(run: StoredRun) -> ActionResult:
    ree_id, run_id = run.ree_id, run.run_id
    if run.context is None:
        raise RuntimeError(f"run {run_id} names no command it started")
    try:
        handle = require_handle(ree_id)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        record = ree_registry.get(ree_id)
        if record is None:
            raise
        handle = ReeRoute(ree_id=ree_id, workbench_id="", store_id=record.store_id)
    following = _following(ree_id, run_id)
    del following["on_started"]
    result = command_dispatcher.follow(
        handle,
        run.context,
        run_id,
        lambda stream, level, message: append_run_log(ree_id, run_id, stream, level, message),
        after=run.log_offset,
        **following,
    )
    if not result.outputs and run.outputs:
        return result.model_copy(update={"outputs": run.outputs})
    return result


def start_provisioning_run(
    ree_id: str,
    request_payload: dict[str, Any],
    runner: Callable[[str, str], ActionResult],
) -> dict[str, Any]:
    return _registry.start_background(
        ree_id,
        "initialize_ree",
        request_payload,
        runner,
        action="create_ree",
        require_ree_exists=False,
    )


def start_single_command_run(
    ree_id: str,
    *,
    action: AuthorApiActionName | None,
    command: Command,
    request_payload: dict[str, Any],
    canceled_message: str,
    fallback_outputs: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    after_success: Callable[[ReeRoute, ActionResult], ActionResult] | None = None,
) -> dict[str, Any]:
    outputs = dict(fallback_outputs or {})

    def _runner(rid: str, run_id: str) -> ActionResult:
        def _log(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        if is_cancel_requested(rid, run_id):
            _log("system", "warn", canceled_message)
            return ActionResult(status="canceled", outputs=outputs)

        try:
            handle = require_handle(rid)
        except HTTPException as exc:
            _log("system", "error", str(exc.detail))
            return ActionResult.failed(
                "unavailable",
                str(exc.detail),
                origin="api",
                retryable=exc.status_code == 503,
            )

        following = _following(rid, run_id) if after_success is None else {"stop": _registry.stopping}
        try:
            result = command_dispatcher.dispatch_action(handle, command, run_id, _log, **following)
        except ReeBusyError as exc:
            _log("system", "error", str(exc))
            return ActionResult.failed(
                "conflict", str(exc), origin="workbench", retryable=True, details={"code": "ree_busy"}
            )
        if result.status == "succeeded" and after_success is not None:
            completed = result
            try:
                result = after_success(handle, completed)
            except Exception as exc:  # noqa: BLE001
                result = ActionResult.failed(
                    "internal", f"Post-execution processing failed: {exc}", origin="api", outputs=completed.outputs
                )
            result = result.model_copy(update={"context": completed.context, "history": completed.history})
        if not result.outputs and outputs:
            return result.model_copy(update={"outputs": outputs})
        return result

    return start_background_run(
        ree_id,
        command.operation,
        request_payload,
        _runner,
        action=action,
        idempotency_key=idempotency_key,
        initial_outputs=outputs,
        resumable=after_success is None,
    )
