from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from repo2ree_api.control.run_orchestration import (
    append_run_log,
    is_cancel_requested,
    start_background_run,
    update_run_outputs,
)
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.storage import author_actions
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    discard_expired_uploads,
    discard_staged_upload,
    staged_upload_path,
    upload_action_id,
    validate_upload_owner,
)
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.command import Command
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import ReeRoute
from repo2ree_telemetry.behaviour.events import AuthorApiActionName


@dataclass(frozen=True)
class StagedUploadLog:
    starting: str
    canceled: str
    copied: str
    succeeded: str


def start_staged_upload_run(
    ree_id: str,
    *,
    upload_token: str,
    archive_name: str,
    purpose: str,
    action: AuthorApiActionName,
    command: Command,
    request_payload: dict[str, Any],
    messages: StagedUploadLog,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    opened = upload_action_id(upload_token)
    action_id = (
        opened if opened is not None and author_actions.is_open(opened) else author_actions.start(action, ree_id)
    )
    try:
        return _start(
            ree_id,
            upload_token=upload_token,
            archive_name=archive_name,
            purpose=purpose,
            action=action,
            action_id=action_id,
            command=command,
            request_payload=request_payload,
            messages=messages,
            idempotency_key=idempotency_key,
        )
    except BaseException as exc:
        author_actions.settle(action_id, "failed", http_status=author_actions.http_status(exc))
        raise


def _start(
    ree_id: str,
    *,
    upload_token: str,
    archive_name: str,
    purpose: str,
    action: AuthorApiActionName,
    action_id: str,
    command: Command,
    request_payload: dict[str, Any],
    messages: StagedUploadLog,
    idempotency_key: str | None,
) -> dict[str, Any]:
    handle = require_handle(ree_id)
    try:
        validate_upload_owner(upload_token, ree_id=ree_id, purpose=purpose, file_name=archive_name)
        staged_host = staged_upload_path(upload_token)
    except (InvalidUploadTokenError, UploadSizeMismatchError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownUploadTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _runner(ws_id: str, run_id: str) -> ActionResult:
        def _log_run(stream: str, level: str, message: str) -> None:
            append_run_log(ws_id, run_id, stream, level, message)

        _log_run("system", "info", messages.starting)
        if is_cancel_requested(ws_id, run_id):
            _log_run("system", "warn", messages.canceled)
            return ActionResult(status="canceled", outputs=request_payload)

        copy_failure = _copy_into_workbench(
            handle,
            upload_token,
            staged_host,
            log_run=_log_run,
            outputs=request_payload,
        )
        if copy_failure is not None:
            return copy_failure
        _log_run("system", "info", messages.copied)

        try:
            result = command_dispatcher.dispatch_action(handle, command, run_id, _log_run)
            if result.outputs:
                update_run_outputs(ws_id, run_id, result.outputs)
        finally:
            discard_staged_upload(upload_token)

        outputs = {**request_payload, **(result.outputs or {})}
        if result.status != "succeeded":
            _log_run("system", "error", f"Workbench step {command.operation} {result.status}")
            return result.model_copy(update={"outputs": outputs})
        _log_run("system", "info", messages.succeeded)
        return result.model_copy(update={"outputs": outputs})

    return start_background_run(
        ree_id,
        command.operation,
        request_payload,
        _runner,
        action=action,
        action_id=action_id,
        idempotency_key=idempotency_key,
    )


def _copy_into_workbench(
    handle: ReeRoute,
    upload_token: str,
    staged_host: Path,
    *,
    log_run: LogSink,
    outputs: dict[str, Any],
) -> ActionResult | None:
    discard_expired_uploads()
    if not staged_host.exists() or staged_host.stat().st_size == 0:
        log_run("system", "error", "Staged upload not found, empty, or expired")
        return ActionResult.failed(
            "precondition",
            "Staged upload not found, empty, or expired",
            origin="api",
            outputs=outputs,
        )
    size = staged_host.stat().st_size
    log_run("system", "info", f"Copying staged archive into the workbench ({size} bytes)")
    try:
        command_dispatcher.copy_to_workbench(handle, str(staged_host), f"upload-staging/{upload_token}.bin")
    except Exception as exc:  # noqa: BLE001
        log_run("system", "error", f"Copy to workbench failed: {exc}")
        return ActionResult.failed(
            "unavailable",
            f"Copy to workbench failed: {exc}",
            origin="supervisor",
            retryable=True,
            outputs=outputs,
        )
    return None
