"""Shared HTTP upload staging and workbench-transfer operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_commands import require_handle
from repo2ree_api.schemas import UploadInitPayload
from repo2ree_api.settings import service_settings
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    UploadStagingFullError,
    UploadTooLargeError,
    discard_expired_uploads,
    new_upload_token,
    stage_upload_stream,
    validate_upload_owner,
)
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchHandle


def mint_upload_token(ree_id: str, payload: UploadInitPayload, *, upload_route: str, purpose: str) -> dict[str, Any]:
    require_handle(ree_id)
    if payload.size > service_settings.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "upload_too_large",
                "message": f"Upload exceeds the {service_settings.UPLOAD_MAX_BYTES}-byte limit",
                "details": {"declared_size": payload.size, "max_bytes": service_settings.UPLOAD_MAX_BYTES},
            },
        )
    result = new_upload_token(
        file_name=payload.file_name,
        expected_size=payload.size,
        content_type=payload.content_type,
        ree_id=ree_id,
        purpose=purpose,
    )
    result["upload_url"] = f"/api/v1/rees/{ree_id}/{upload_route}/{result['upload_token']}"
    return result


async def stage_upload_bytes(ree_id: str, upload_token: str, request: Request, *, purpose: str) -> dict[str, Any]:
    await asyncio.to_thread(require_handle, ree_id)
    try:
        validate_upload_owner(upload_token, ree_id=ree_id, purpose=purpose)
        await stage_upload_stream(upload_token, request.stream())
    except InvalidUploadTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownUploadTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UploadStagingFullError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    except UploadSizeMismatchError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "upload_size_mismatch", "message": str(exc), "details": None},
        ) from exc
    return {"upload_token": upload_token, "stored_at": utc_now()}


def copy_staged_upload_into_workbench(
    handle: WorkbenchHandle,
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
        workbench_manager.copy_to_workbench(handle, str(staged_host), f"/ree/upload-staging/{upload_token}.bin")
    except Exception as exc:
        log_run("system", "error", f"Copy to workbench failed: {exc}")
        return ActionResult.failed(
            "unavailable",
            f"Copy to workbench failed: {exc}",
            origin="supervisor",
            retryable=True,
            outputs=outputs,
        )
    return None
