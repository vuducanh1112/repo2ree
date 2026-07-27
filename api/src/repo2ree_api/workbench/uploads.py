"""The staging half of the two-phase upload: mint a slot, then receive bytes.

Everything here runs on the request thread and answers to the client that is
uploading: it validates the declared size, claims a token for one REE and one
purpose, and streams the body onto control-plane disk. Nothing here touches a
workbench or starts a run — handing staged bytes to the REE is the other half,
in :mod:`repo2ree_api.workbench.upload_runs`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, Request

from repo2ree_api.contracts import UploadInitPayload
from repo2ree_api.settings import service_settings
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    UploadStagingFullError,
    UploadTooLargeError,
    new_upload_token,
    stage_upload_stream,
    validate_upload_owner,
)
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.time_utils import utc_now


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
