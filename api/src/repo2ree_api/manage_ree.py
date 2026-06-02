from datetime import datetime, timezone
import logging
import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response

from repo2ree_api.api_utils import paginate
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _run_summary,
    _start_background_run,
    _update_run_outputs,
)
from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_core.envelope import (
    AcquireSourceCommand,
    DeleteFileCommand,
    ExtractUploadCommand,
    MaterializeWorkspaceCommand,
    PatchReeDraftCommand,
    RemoveSourceCommand,
    SnapshotUpstreamCommand,
    UpdateSourceMetadataCommand,
    WriteFileCommand,
)
from repo2ree_core.envelope.command import (
    AcquireSourceArgs,
    Command,
    DeleteFileArgs,
    ExtractUploadArgs,
    PatchReeDraftArgs,
    UpdateSourceMetadataArgs,
    WriteFileArgs,
)
from repo2ree_core.storage.layout import WORKBENCH_ROOT, ReeLayout
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
    workspace_root,
    write_file_content,
)


_log = logging.getLogger(__name__)


def _mirror_to_workbench(ree_id: str, cmd: Command) -> None:
    """Fire a single command at the workbench for a registered REE.

    Non-fatal: logs a warning on failure so the host-side response is never
    affected. Used by synchronous routes that mirror writes into the volume.
    """
    handle = workbench_manager.lookup(ree_id)
    if handle is None:
        return
    try:

        def _log_to_logger(stream: str, level: str, message: str) -> None:
            _log.info("workbench mirror %s %s: %s", stream, level, message)

        result = workbench_manager.dispatch_action(
            handle, cmd, f"mirror-{cmd.operation}", _log_to_logger
        )  # type: ignore[arg-type]
        if result.status != "succeeded":
            _log.warning(
                "workbench mirror %s %s for %s", cmd.operation, result.status, ree_id
            )
    except Exception as exc:
        _log.warning(
            "workbench mirror %s failed for %s: %s", cmd.operation, ree_id, exc
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
        result = create_workspace(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Provision a workbench for every REE except the legacy "url" mode
    # (which already acquires source inline on the host side). Failure is
    # non-fatal — the host-side flow remains the fallback until all routes
    # are migrated to the workbench path.
    if payload.sourceMode != "url":
        ree_id = result["reeId"]
        name = payload.name or ree_id[:8]
        try:
            workbench_manager.provision(ree_id, name)
        except Exception as exc:
            _log.warning("workbench provision failed for %s: %s", ree_id, exc)

    return result


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
        result = patch_ree_draft(ree_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _mirror_to_workbench(
        ree_id,
        PatchReeDraftCommand(
            args=PatchReeDraftArgs(patch=dict(payload.reePatch or {}))
        ),
    )
    return result


@manage_ree_router.delete("/api/v1/rees/{ree_id}")
def delete_workspace_route(ree_id: str):
    try:
        delete_workspace(ree_id)

        handle = workbench_manager.lookup(ree_id)
        if handle is not None:
            try:
                workbench_manager.teardown(handle)
            except Exception as exc:
                _log.warning("workbench teardown failed for %s: %s", ree_id, exc)

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

        handle = workbench_manager.lookup(ree_id)

        def _runner(ws_id: str, run_id: str):
            def _log(stream: str, level: str, message: str) -> None:
                _append_run_log(ws_id, run_id, stream, level, message)

            _log(
                "system",
                "info",
                f"Starting source acquisition from {payload.originUrl}",
            )
            if _is_cancel_requested(ws_id, run_id):
                _log("system", "warn", "Source acquisition canceled")
                return "canceled", request_payload

            # Host-side — always runs; keeps the frontend up to date.
            acquire_source(ws_id, payload)

            # Workbench-side — runs in parallel if a workbench is registered.
            # Updates the volume so the REE state is observable via docker exec.
            if handle is not None:
                pipeline: list[Command] = [
                    AcquireSourceCommand(
                        args=AcquireSourceArgs(
                            origin_url=payload.originUrl,
                            source_type=payload.sourceType,  # type: ignore[arg-type]
                            dest=WORKBENCH_ROOT / "upstream",
                        )
                    ),
                    SnapshotUpstreamCommand(),
                    MaterializeWorkspaceCommand(),
                    UpdateSourceMetadataCommand(
                        args=UpdateSourceMetadataArgs(
                            origin_url=payload.originUrl,
                            source_type=payload.sourceType,
                        )
                    ),
                ]
                for cmd in pipeline:
                    result = workbench_manager.dispatch_action(
                        handle, cmd, run_id, _log
                    )
                    if result.outputs:
                        _update_run_outputs(ws_id, run_id, result.outputs)
                    if result.status != "succeeded":
                        _log(
                            "system",
                            "warn",
                            f"Workbench step {cmd.operation} {result.status} — host-side succeeded",
                        )
                        break

            _log("system", "info", "Source acquisition succeeded")
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

        handle = workbench_manager.lookup(ree_id)
        staged_host = ReeLayout.for_ree(workspace_root(), ree_id).upload_staging_file(
            payload.uploadToken
        )

        def _runner(ws_id: str, run_id: str):
            def _log(stream: str, level: str, message: str) -> None:
                _append_run_log(ws_id, run_id, stream, level, message)

            _log(
                "system",
                "info",
                f"Starting source upload extraction for {payload.archiveName}",
            )
            if _is_cancel_requested(ws_id, run_id):
                _log("system", "warn", "Source upload canceled")
                return "canceled", request_payload

            # Workbench-side copy must happen before the host-side call because
            # complete_source_upload deletes the staged file after extracting it.
            if handle is not None:
                try:
                    workbench_manager.copy_to_workbench(
                        handle,
                        str(staged_host),
                        f"/ree/upload-staging/{payload.uploadToken}.bin",
                    )
                except Exception as exc:
                    _log("system", "warn", f"docker cp to workbench failed: {exc}")
                    handle_for_pipeline = None
                else:
                    handle_for_pipeline = handle
            else:
                handle_for_pipeline = None

            # Host-side — always runs; keeps the frontend up to date.
            complete_source_upload(ws_id, payload.uploadToken, payload.archiveName)

            # Workbench-side pipeline — runs if the copy succeeded.
            if handle_for_pipeline is not None:
                pipeline: list[Command] = [
                    ExtractUploadCommand(
                        args=ExtractUploadArgs(
                            upload_token=payload.uploadToken,
                            archive_name=payload.archiveName,
                        )
                    ),
                    SnapshotUpstreamCommand(),
                    MaterializeWorkspaceCommand(),
                    UpdateSourceMetadataCommand(
                        args=UpdateSourceMetadataArgs(
                            mode="upload",
                            archive_name=payload.archiveName,
                            upload_token=payload.uploadToken,
                        )
                    ),
                ]
                for cmd in pipeline:
                    result = workbench_manager.dispatch_action(
                        handle_for_pipeline, cmd, run_id, _log
                    )
                    if result.outputs:
                        _update_run_outputs(ws_id, run_id, result.outputs)
                    if result.status != "succeeded":
                        _log(
                            "system",
                            "warn",
                            f"Workbench step {cmd.operation} {result.status} — host-side succeeded",
                        )
                        break

            _log("system", "info", "Source upload extraction succeeded")
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
        result = remove_source(ree_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _mirror_to_workbench(ree_id, RemoveSourceCommand())
    return result


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
        result = write_file_content(ree_id, payload.path, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _mirror_to_workbench(
        ree_id,
        WriteFileCommand(
            args=WriteFileArgs(path=payload.path, content=payload.content)
        ),
    )
    return result


@manage_ree_router.delete("/api/v1/rees/{ree_id}/files/content")
def delete_workspace_file_content_route(ree_id: str, path: str = Query(...)):
    try:
        result = delete_file_content(ree_id, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _mirror_to_workbench(ree_id, DeleteFileCommand(args=DeleteFileArgs(path=path)))
    return result


@manage_ree_router.post("/api/v1/rees/{ree_id}/workbench/reprovision")
def reprovision_workbench_route(ree_id: str):
    """Replace the workbench container from the current image, keeping REE volume data."""
    try:
        workbench_manager.reprovision(ree_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "reprovisioned", "reeId": ree_id}


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
