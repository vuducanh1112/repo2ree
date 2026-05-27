from datetime import datetime, timezone
import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response

from repo2ree_api.api_utils import paginate
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree_api.storage.workspace_files import (
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    ReeDraftPatchPayload,
    WorkspaceVersionConflictError,
    build_workspace_ree_archive,
    UploadInitPayload,
    WorkspaceCreatePayload,
    WorkspaceFileContentPayload,
    acquire_source,
    complete_source_upload,
    create_workspace,
    delete_workspace,
    get_workspace,
    init_source_upload,
    list_workspace_metadata,
    read_file_bytes,
    read_workspace_metadata,
    patch_ree_draft,
    remove_source,
    delete_file_content,
    store_source_upload_bytes,
    write_file_content,
)


# ================================================
# Router
# ================================================


manage_ree_router = APIRouter()


# ================================================
# Route Handlers
# ================================================


@manage_ree_router.post("/api/v1/rees")
def create_workspace_route(payload: WorkspaceCreatePayload):
    try:
        return create_workspace(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/rees")
def list_workspaces_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
    status: str | None = Query(None),
):
    items = list_workspace_metadata(status=status)
    page, next_cursor, _has_more = paginate(items, cursor=cursor, limit=limit)
    return {"items": page, "nextCursor": next_cursor}


@manage_ree_router.get("/api/v1/rees/{ree_id}")
def get_workspace_route(ree_id: str):
    try:
        return get_workspace(ree_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.patch("/api/v1/rees/{ree_id}/draft")
def patch_ree_draft_route(ree_id: str, payload: ReeDraftPatchPayload):
    try:
        current = read_workspace_metadata(ree_id)
        if payload.expectedVersion and payload.expectedVersion != current.get(
            "updatedAt"
        ):
            raise HTTPException(
                status_code=409,
                detail="Workspace version conflict",
            )
        return patch_ree_draft(ree_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/rees/{ree_id}")
def delete_workspace_route(ree_id: str):
    try:
        delete_workspace(ree_id)
        return {
            "deletedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "state": "deleted",
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:acquire")
def acquire_source_route(ree_id: str, payload: SourceAcquirePayload):
    try:
        request_payload = {
            "mode": "download",
            "originUrl": payload.originUrl,
            "sourceType": payload.sourceType,
        }

        def _runner(ws_id: str, run_id: str):
            _append_run_log(
                ws_id,
                run_id,
                "system",
                "info",
                f"Starting source acquisition from {payload.originUrl}",
            )
            if _is_cancel_requested(ws_id, run_id):
                _append_run_log(
                    ws_id, run_id, "system", "warn", "Source acquisition canceled"
                )
                return "canceled", request_payload
            acquire_source(ws_id, payload)
            _append_run_log(
                ws_id, run_id, "system", "info", "Source acquisition succeeded"
            )
            return "succeeded", request_payload

        run_state = _start_background_run(
            ree_id=ree_id,
            operation="source",
            request_payload=request_payload,
            run_id_prefix="source",
            runner=_runner,
        )
        return _run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:upload-init")
def upload_init_route(ree_id: str, payload: UploadInitPayload):
    try:
        return init_source_upload(ree_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.put("/api/v1/rees/{ree_id}/source:upload/{upload_token}")
async def store_upload_bytes_route(ree_id: str, upload_token: str, request: Request):
    try:
        data = await request.body()
        return store_source_upload_bytes(ree_id, upload_token, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:upload-complete")
def upload_complete_route(ree_id: str, payload: SourceUploadCompletePayload):
    try:
        request_payload = {
            "mode": "upload",
            "uploadToken": payload.uploadToken,
            "archiveName": payload.archiveName,
        }

        def _runner(ws_id: str, run_id: str):
            _append_run_log(
                ws_id,
                run_id,
                "system",
                "info",
                f"Starting source upload extraction for {payload.archiveName}",
            )
            if _is_cancel_requested(ws_id, run_id):
                _append_run_log(
                    ws_id, run_id, "system", "warn", "Source upload canceled"
                )
                return "canceled", request_payload
            complete_source_upload(ws_id, payload.uploadToken, payload.archiveName)
            _append_run_log(
                ws_id, run_id, "system", "info", "Source upload extraction succeeded"
            )
            return "succeeded", request_payload

        run_state = _start_background_run(
            ree_id=ree_id,
            operation="source",
            request_payload=request_payload,
            run_id_prefix="source",
            runner=_runner,
        )
        return _run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/rees/{ree_id}/source")
def remove_source_route(ree_id: str):
    try:
        return remove_source(ree_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/rees/{ree_id}/files/raw")
def get_workspace_file_raw_route(ree_id: str, path: str = Query(...)):
    try:
        content = read_file_bytes(ree_id, path)
        return Response(content=content, media_type="application/octet-stream")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.put("/api/v1/rees/{ree_id}/files/content")
def put_workspace_file_content_route(ree_id: str, payload: WorkspaceFileContentPayload):
    try:
        return write_file_content(ree_id, payload.path, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/rees/{ree_id}/files/content")
def delete_workspace_file_content_route(ree_id: str, path: str = Query(...)):
    try:
        return delete_file_content(ree_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/rees/{ree_id}/ree-archive")
def download_workspace_ree_archive_route(ree_id: str):
    try:
        archive_bytes = build_workspace_ree_archive(ree_id)
        archive_filename = _archive_download_filename(ree_id)
        return Response(
            content=archive_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{archive_filename}"; '
                    f"filename*=UTF-8''{quote(archive_filename)}"
                )
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ================================================
# Helpers
# ================================================


def _archive_download_filename(ree_id: str) -> str:
    metadata = read_workspace_metadata(ree_id)
    raw_name = str(metadata.get("name") or "").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    if not safe_stem:
        safe_stem = "ree"
    return f"{safe_stem}.zip"
