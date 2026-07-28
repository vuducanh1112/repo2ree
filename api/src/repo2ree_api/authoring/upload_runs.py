"""The consuming half of the two-phase upload: staged bytes become REE work.

Where :mod:`repo2ree_api.workbench.uploads` leaves an archive on control-plane disk,
this module hands it to the workbench: claim the token for this REE and purpose,
copy the bytes in, run one command over them, and reclaim the host copy. It runs
in the background — the client polls the returned run — so the only HTTP here is
the up-front rejection of a token that was never valid to begin with.

Both staged-upload routes (a source archive, a whole REE bundle) are this one
sequence with a different command and different words in the log; the sequence
itself lives here once, because a change to how ownership of the bytes transfers
must not be able to apply to one of them and not the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from repo2ree_api.contracts import RunOperation
from repo2ree_api.control.run_orchestration import (
    append_run_log,
    is_cancel_requested,
    start_background_run,
    update_run_outputs,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    discard_expired_uploads,
    discard_staged_upload,
    staged_upload_path,
    validate_upload_owner,
)
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.command import Command
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchHandle


@dataclass(frozen=True)
class StagedUploadLog:
    """How one staged-upload run narrates itself in its log stream.

    Spelled per run rather than derived from the operation: these lines are read
    by a human watching a transfer, and "restoring it into the REE" and
    "extracting into the workspace" describe genuinely different things.
    """

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
    operation: RunOperation,
    run_id_prefix: str,
    command: Command,
    request_payload: dict[str, Any],
    messages: StagedUploadLog,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Start the background run that hands a staged upload to the workbench.

    The token is claimed on the request thread, so a token that never belonged
    to this REE and purpose fails the caller's own POST instead of a run they
    then have to poll to discover was doomed.

    Run outputs are what the caller asked for, overlaid with whatever the command
    reported — so a run always echoes its own request even when the command said
    nothing, and never hides what the command found.
    """
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
            result = workbench_manager.dispatch_action(handle, command, run_id, _log_run)
            if result.outputs:
                update_run_outputs(ws_id, run_id, result.outputs)
        finally:
            # Ownership transferred to the workbench; always reclaim the host copy.
            discard_staged_upload(upload_token)

        outputs = {**request_payload, **(result.outputs or {})}
        if result.status != "succeeded":
            _log_run("system", "error", f"Workbench step {command.operation} {result.status}")
            return result.model_copy(update={"outputs": outputs})
        _log_run("system", "info", messages.succeeded)
        return ActionResult(status="succeeded", outputs=outputs)

    return start_background_run(
        ree_id,
        operation,
        request_payload,
        run_id_prefix,
        _runner,
        idempotency_key=idempotency_key,
    )


def _copy_into_workbench(
    handle: WorkbenchHandle,
    upload_token: str,
    staged_host: Path,
    *,
    log_run: LogSink,
    outputs: dict[str, Any],
) -> ActionResult | None:
    """Copy the staged archive into the workbench, or report why it could not be.

    Returns the terminal ActionResult on failure and None on success, so the
    caller's happy path stays linear. Expired staging is swept first: a token
    that outlived its window is indistinguishable here from one that was never
    written, and both are the caller's problem rather than the workbench's.
    """
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
        workbench_manager.copy_to_workbench(handle, str(staged_host), f"/ree/upload-staging/{upload_token}.bin")
    except Exception as exc:  # noqa: BLE001 — the transfer is the workbench's, so any failure is reported as an unavailable run
        log_run("system", "error", f"Copy to workbench failed: {exc}")
        return ActionResult.failed(
            "unavailable",
            f"Copy to workbench failed: {exc}",
            origin="supervisor",
            retryable=True,
            outputs=outputs,
        )
    return None
