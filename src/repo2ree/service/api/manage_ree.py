from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from repo2ree.service.api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
)
from repo2ree.service.api.settings import service_settings
from repo2ree.service.metadata.database import get_session
from repo2ree.service.metadata.ree_record import REERecord
from repo2ree.service.storage.workspace_files import (
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    build_workspace_ree_archive,
    UploadInitPayload,
    WorkspaceCreatePayload,
    WorkspaceFileContentPayload,
    WorkspacePatchPayload,
    acquire_source,
    complete_source_upload,
    create_workspace,
    delete_workspace,
    get_workspace,
    init_source_upload,
    list_files,
    list_workspace_metadata,
    read_file_content,
    read_file_bytes,
    read_workspace_metadata,
    patch_workspace,
    remove_source,
    delete_file_content,
    store_source_upload_bytes,
    write_file_content,
)

manage_ree_router = APIRouter()


@manage_ree_router.get("/api/ree")
def list_rees(session: Session = Depends(get_session)):
    """Return a list of available REEs from the metadata DB.

    Each item mirrors the fields on `REERecord` so the frontend can
    display names and link to blob hashes.
    """
    records = session.exec(select(REERecord)).all()
    return [r.dict() for r in records]


@manage_ree_router.get("/api/ree/{ree_id}")
def get_ree(ree_id: int, session: Session = Depends(get_session)):
    ree_record = session.get(REERecord, ree_id)
    if not ree_record:
        raise HTTPException(status_code=404, detail="REE not found")

    # Build a list of file entries based on hashes/names stored on the record.
    files = []

    def add_file_entry(hash_val: str, filename: str):
        if not hash_val:
            return
        blob_path = service_settings.BLOB_STORAGE_DIR / hash_val
        size = None
        if blob_path.exists():
            try:
                size = blob_path.stat().st_size
            except Exception:
                size = None
        files.append(
            {
                "hash": hash_val,
                "name": filename or hash_val,
                "size": f"{size} bytes" if size is not None else "",
                "url": f"/api/blob/{hash_val}?name={filename}",
            }
        )

    add_file_entry(ree_record.project_files_hash, ree_record.project_files_name)
    add_file_entry(ree_record.runtime_hash, ree_record.runtime_name)
    add_file_entry(
        ree_record.build_runtime_script_hash, ree_record.build_runtime_script_name
    )
    add_file_entry(ree_record.sbom_file_hash, ree_record.sbom_file_name)
    add_file_entry(
        ree_record.validate_runtime_reproducibility_script_hash,
        ree_record.validate_runtime_reproducibility_script_name,
    )
    # include the produced REE archive if present
    add_file_entry(ree_record.archive_hash, "ree.tar.gz")

    result = ree_record.dict()
    result["files"] = files
    return result


@manage_ree_router.get("/api/blob/{hash_val}")
def serve_blob(hash_val: str, name: str | None = Query(None)):
    """Serve a blob file identified by its content hash."""
    blob_path = service_settings.BLOB_STORAGE_DIR / hash_val
    if not blob_path.exists():
        raise HTTPException(status_code=404, detail="Blob not found")

    filename = name or blob_path.name
    return FileResponse(
        path=blob_path, filename=filename, media_type="application/octet-stream"
    )


def _paginate_items(
    items: list[dict], cursor: str | None = None, limit: int | None = None
):
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
    next_cursor = str(end) if end < len(items) else None
    return page, next_cursor


@manage_ree_router.post("/api/v1/workspaces")
def create_workspace_route(payload: WorkspaceCreatePayload):
    try:
        return create_workspace(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/workspaces")
def list_workspaces_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
    status: str | None = Query(None),
):
    items = list_workspace_metadata(status=status)
    page, next_cursor = _paginate_items(items, cursor=cursor, limit=limit)
    return {"items": page, "nextCursor": next_cursor}


@manage_ree_router.get("/api/v1/workspaces/{workspace_id}")
def get_workspace_route(workspace_id: str):
    try:
        return get_workspace(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.patch("/api/v1/workspaces/{workspace_id}")
def patch_workspace_route(workspace_id: str, payload: WorkspacePatchPayload):
    try:
        current = read_workspace_metadata(workspace_id)
        if payload.expectedVersion and payload.expectedVersion != current.get(
            "updatedAt"
        ):
            raise HTTPException(
                status_code=409,
                detail="Workspace version conflict",
            )
        return patch_workspace(workspace_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/workspaces/{workspace_id}")
def delete_workspace_route(workspace_id: str):
    try:
        delete_workspace(workspace_id)
        return {
            "deletedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "state": "deleted",
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.post("/api/v1/workspaces/{workspace_id}/source:acquire")
def acquire_source_route(workspace_id: str, payload: SourceAcquirePayload):
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
            workspace_id=workspace_id,
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


@manage_ree_router.post("/api/v1/workspaces/{workspace_id}/source:upload-init")
def upload_init_route(workspace_id: str, payload: UploadInitPayload):
    try:
        return init_source_upload(workspace_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.put("/api/v1/workspaces/{workspace_id}/source:upload/{upload_token}")
async def store_upload_bytes_route(
    workspace_id: str, upload_token: str, request: Request
):
    try:
        data = await request.body()
        return store_source_upload_bytes(workspace_id, upload_token, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.post("/api/v1/workspaces/{workspace_id}/source:upload-complete")
def upload_complete_route(workspace_id: str, payload: SourceUploadCompletePayload):
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
            workspace_id=workspace_id,
            operation="source",
            request_payload=request_payload,
            run_id_prefix="source",
            runner=_runner,
        )
        return _run_summary(run_state)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/workspaces/{workspace_id}/source")
def remove_source_route(workspace_id: str):
    try:
        return remove_source(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/workspaces/{workspace_id}/files")
def list_workspace_files_route(
    workspace_id: str,
    path: str | None = Query(None),
    recursive: bool | None = Query(None),
    scope: str | None = Query(None),
):
    try:
        files = list_files(workspace_id)
        if path:
            normalized = path.strip("/")
            files = [
                item
                for item in files
                if item["path"] == normalized
                or item["path"].startswith(f"{normalized}/")
            ]
        if scope == "source":
            files = [item for item in files if item["kind"] == "source"]
        elif scope == "generated":
            files = [item for item in files if item["kind"] == "generated"]
        return {"nodes": files}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/workspaces/{workspace_id}/files/content")
def get_workspace_file_content_route(workspace_id: str, path: str = Query(...)):
    try:
        return read_file_content(workspace_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/workspaces/{workspace_id}/files/raw")
def get_workspace_file_raw_route(workspace_id: str, path: str = Query(...)):
    try:
        content = read_file_bytes(workspace_id, path)
        return Response(content=content, media_type="application/octet-stream")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.put("/api/v1/workspaces/{workspace_id}/files/content")
def put_workspace_file_content_route(
    workspace_id: str, payload: WorkspaceFileContentPayload
):
    try:
        return write_file_content(workspace_id, payload.path, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.delete("/api/v1/workspaces/{workspace_id}/files/content")
def delete_workspace_file_content_route(workspace_id: str, path: str = Query(...)):
    try:
        return delete_file_content(workspace_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@manage_ree_router.get("/api/v1/workspaces/{workspace_id}/ree-archive")
def download_workspace_ree_archive_route(workspace_id: str):
    try:
        archive_bytes = build_workspace_ree_archive(workspace_id)
        return Response(content=archive_bytes, media_type="application/zip")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
