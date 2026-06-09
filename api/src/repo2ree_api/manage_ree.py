import logging
import re
import uuid
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
from repo2ree_api.schemas import (
    ReeIntentPatchPayload,
    ReeSealPayload,
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    UploadInitPayload,
    WorkspaceCreatePayload,
    WorkspaceFileContentPayload,
)
from repo2ree_api.storage.upload_staging import (
    discard_staged_upload,
    new_upload_token,
    stage_upload_bytes,
    staged_upload_path,
)
from repo2ree_api.workbench.deps import workbench_manager
from repo2ree_core.storage.layout import WORKBENCH_ROOT
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol import (
    AcquireSourceCommand,
    ActionResult,
    DeleteFileCommand,
    ExtractUploadCommand,
    MaterializeWorkspaceCommand,
    PatchReeIntentCommand,
    RemoveSourceCommand,
    SnapshotUpstreamCommand,
    UpdateSourceMetadataCommand,
    WriteFileCommand,
)
from repo2ree_protocol.command import (
    AcquireSourceArgs,
    Command,
    DeleteFileArgs,
    ExtractUploadArgs,
    PatchReeIntentArgs,
    UpdateSourceMetadataArgs,
    WriteFileArgs,
)
from repo2ree_supervisor import WorkbenchHandle, WorkbenchUnavailableError

# ================================================
# Logging
# ================================================


_log = logging.getLogger(__name__)


# ================================================
# Utility Functions
# ================================================


def _require_handle(ree_id: str) -> WorkbenchHandle:
    """Return the workbench handle for ree_id or raise.

    404 if no workbench is registered for the REE; 503 if one is registered
    but its container is not currently reachable. The workbench volume is the
    single source of truth — there is no host-side fallback.
    """
    handle = workbench_manager.lookup(ree_id)
    if handle is not None:
        return handle
    if workbench_manager.is_registered(ree_id):
        raise HTTPException(status_code=503, detail="Workbench unavailable for this REE")
    raise HTTPException(status_code=404, detail=f"REE {ree_id} not found")


def _dispatch_or_500(handle: WorkbenchHandle, cmd: Command, run_id: str, error_detail: str) -> ActionResult:
    """Dispatch a single workbench command, raising HTTP 500 unless it succeeds."""
    result = workbench_manager.dispatch_action(handle, cmd, run_id, lambda *_: None)
    if result.status != "succeeded":
        raise HTTPException(status_code=500, detail=error_detail)
    return result


def _source_pipeline(lead: Command, metadata_args: UpdateSourceMetadataArgs) -> list[Command]:
    """Build the standard source pipeline: <lead> → snapshot → materialize → update-metadata."""
    return [
        lead,
        SnapshotUpstreamCommand(),
        MaterializeWorkspaceCommand(),
        UpdateSourceMetadataCommand(args=metadata_args),
    ]


def _run_source_pipeline(
    handle: WorkbenchHandle,
    ws_id: str,
    run_id: str,
    pipeline: list[Command],
    log_run,
) -> str:
    """Dispatch each command in order, recording outputs and stopping on first non-success.

    Returns the final status ("succeeded" or the failing step's status).
    """
    for cmd in pipeline:
        result = workbench_manager.dispatch_action(handle, cmd, run_id, log_run)
        if result.outputs:
            _update_run_outputs(ws_id, run_id, result.outputs)
        if result.status != "succeeded":
            log_run("system", "error", f"Workbench step {cmd.operation} {result.status}")
            return result.status
    return "succeeded"


def _run_workbench_acquire_pipeline(
    handle: WorkbenchHandle,
    ree_id: str,
    *,
    origin_url: str,
    source_type: str,
) -> None:
    """Run the acquire → snapshot → materialize → update-metadata pipeline in the workbench.

    Non-fatal: logs warnings and stops the pipeline on first failure so the
    caller's response is not affected.
    """
    pipeline = _source_pipeline(
        AcquireSourceCommand(
            args=AcquireSourceArgs(
                origin_url=origin_url,
                source_type=source_type,  # type: ignore[arg-type]
                dest=WORKBENCH_ROOT / "upstream",
            )
        ),
        UpdateSourceMetadataArgs(origin_url=origin_url, source_type=source_type),
    )
    for cmd in pipeline:
        try:
            result = workbench_manager.dispatch_action(handle, cmd, f"init-{cmd.operation}", lambda *_: None)
        except Exception as exc:
            _log.warning(
                "workbench acquire pipeline %s failed for %s: %s",
                cmd.operation,
                ree_id,
                exc,
            )
            break
        if result.status != "succeeded":
            _log.warning(
                "workbench acquire pipeline %s %s for %s",
                cmd.operation,
                result.status,
                ree_id,
            )
            break


# ================================================
# Router
# ================================================


manage_ree_router = APIRouter()


# ================================================
# Route Handlers
# ================================================


@manage_ree_router.post("/api/v1/rees")
def create_workspace_route(payload: WorkspaceCreatePayload):
    if payload.sourceMode == "url" and not payload.originUrl:
        raise HTTPException(status_code=400, detail="originUrl is required for url source mode")

    ree_id = uuid.uuid4().hex
    name = payload.name or ree_id[:8]

    try:
        handle = workbench_manager.provision(ree_id, name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbench provisioning failed: {exc}") from exc

    # For url mode, acquire the source synchronously into the workbench volume
    # so the response reflects acquired state.
    if payload.sourceMode == "url" and payload.originUrl:
        _run_workbench_acquire_pipeline(
            handle,
            ree_id,
            origin_url=payload.originUrl,
            source_type=payload.sourceType or "git",
        )

    return workbench_manager.get_workspace(handle)


@manage_ree_router.get("/api/v1/rees")
def list_workspaces_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None),
    status: str | None = Query(None),
):
    items = workbench_manager.list_all_metadata()
    if status:
        items = [m for m in items if m.get("status") == status]
    page, next_cursor, _has_more = paginate(items, cursor=cursor, limit=limit)
    return {"items": page, "nextCursor": next_cursor}


@manage_ree_router.get("/api/v1/rees/{ree_id}")
def get_workspace_route(ree_id: str):
    handle = _require_handle(ree_id)
    return workbench_manager.get_workspace(handle)


@manage_ree_router.patch("/api/v1/rees/{ree_id}/intent")
def patch_ree_intent_route(ree_id: str, payload: ReeIntentPatchPayload):
    handle = _require_handle(ree_id)
    current = workbench_manager.get_ree_metadata(handle)
    if payload.expectedVersion and payload.expectedVersion != current.get("updatedAt"):
        raise HTTPException(status_code=409, detail="Workspace version conflict")

    cmd = PatchReeIntentCommand(args=PatchReeIntentArgs(patch=dict(payload.reeIntentPatch or {})))
    _dispatch_or_500(handle, cmd, "patch-intent", "Workbench patch_ree_intent failed")
    return workbench_manager.get_workspace(handle)


@manage_ree_router.delete("/api/v1/rees/{ree_id}")
def delete_workspace_route(ree_id: str):
    handle = _require_handle(ree_id)
    try:
        workbench_manager.teardown(handle)
    except Exception as exc:
        _log.warning("workbench teardown failed for %s: %s", ree_id, exc)
        raise HTTPException(status_code=500, detail=f"Workbench teardown failed: {exc}") from exc
    return {
        "deletedAt": utc_now(),
        "state": "deleted",
    }


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:acquire")
def acquire_source_route(ree_id: str, payload: SourceAcquirePayload):
    handle = _require_handle(ree_id)
    request_payload = {
        "mode": "download",
        "originUrl": payload.originUrl,
        "sourceType": payload.sourceType,
    }

    def _runner(ws_id: str, run_id: str):
        def _log_run(stream: str, level: str, message: str) -> None:
            _append_run_log(ws_id, run_id, stream, level, message)

        _log_run(
            "system",
            "info",
            f"Starting source acquisition from {payload.originUrl}",
        )
        if _is_cancel_requested(ws_id, run_id):
            _log_run("system", "warn", "Source acquisition canceled")
            return "canceled", request_payload

        pipeline = _source_pipeline(
            AcquireSourceCommand(
                args=AcquireSourceArgs(
                    origin_url=payload.originUrl,
                    source_type=payload.sourceType,  # type: ignore[arg-type]
                    dest=WORKBENCH_ROOT / "upstream",
                )
            ),
            UpdateSourceMetadataArgs(
                origin_url=payload.originUrl,
                source_type=payload.sourceType,
            ),
        )
        status = _run_source_pipeline(handle, ws_id, run_id, pipeline, _log_run)
        if status != "succeeded":
            return status, request_payload

        _log_run("system", "info", "Source acquisition succeeded")
        return "succeeded", request_payload

    run_state = _start_background_run(
        ree_id=ree_id,
        operation="source",
        request_payload=request_payload,
        run_id_prefix="source",
        runner=_runner,
    )

    return _run_summary(run_state)


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:upload-init")
def upload_init_route(ree_id: str, payload: UploadInitPayload):
    _require_handle(ree_id)
    result = new_upload_token()
    token = result["uploadToken"]
    result["uploadUrl"] = f"/api/v1/rees/{ree_id}/source:upload/{token}"
    return result


@manage_ree_router.put("/api/v1/rees/{ree_id}/source:upload/{upload_token}")
async def store_upload_bytes_route(ree_id: str, upload_token: str, request: Request):
    _require_handle(ree_id)
    data = await request.body()
    stage_upload_bytes(upload_token, data)
    return {
        "uploadToken": upload_token,
        "storedAt": utc_now(),
    }


@manage_ree_router.post("/api/v1/rees/{ree_id}/source:upload-complete")
def upload_complete_route(ree_id: str, payload: SourceUploadCompletePayload):
    handle = _require_handle(ree_id)
    request_payload = {
        "mode": "upload",
        "uploadToken": payload.uploadToken,
        "archiveName": payload.archiveName,
    }
    staged_host = staged_upload_path(payload.uploadToken)

    def _runner(ws_id: str, run_id: str):
        def _log_run(stream: str, level: str, message: str) -> None:
            _append_run_log(ws_id, run_id, stream, level, message)

        _log_run(
            "system",
            "info",
            f"Starting source upload extraction for {payload.archiveName}",
        )
        if _is_cancel_requested(ws_id, run_id):
            _log_run("system", "warn", "Source upload canceled")
            return "canceled", request_payload

        if not staged_host.exists():
            _log_run("system", "error", "Staged upload not found")
            return "failed", request_payload

        try:
            workbench_manager.copy_to_workbench(
                handle,
                str(staged_host),
                f"/ree/upload-staging/{payload.uploadToken}.bin",
            )
        except Exception as exc:
            _log_run("system", "error", f"docker cp to workbench failed: {exc}")
            return "failed", request_payload

        pipeline = _source_pipeline(
            ExtractUploadCommand(
                args=ExtractUploadArgs(
                    upload_token=payload.uploadToken,
                    archive_name=payload.archiveName,
                )
            ),
            UpdateSourceMetadataArgs(
                mode="upload",
                archive_name=payload.archiveName,
                upload_token=payload.uploadToken,
            ),
        )
        status = _run_source_pipeline(handle, ws_id, run_id, pipeline, _log_run)

        # Clean up the transient host landing file regardless of outcome.
        discard_staged_upload(payload.uploadToken)

        if status == "succeeded":
            _log_run("system", "info", "Source upload extraction succeeded")
        return status, request_payload

    run_state = _start_background_run(
        ree_id=ree_id,
        operation="source",
        request_payload=request_payload,
        run_id_prefix="source",
        runner=_runner,
    )

    return _run_summary(run_state)


@manage_ree_router.delete("/api/v1/rees/{ree_id}/source")
def remove_source_route(ree_id: str):
    handle = _require_handle(ree_id)
    _dispatch_or_500(handle, RemoveSourceCommand(), "remove-source", "Workbench remove_source failed")
    return {
        "invalidatedSteps": ["source", "evaluate", "workflow"],
        "workspace": workbench_manager.get_workspace(handle),
    }


@manage_ree_router.get("/api/v1/rees/{ree_id}/files/raw")
def get_workspace_file_raw_route(ree_id: str, path: str = Query(...)):
    handle = _require_handle(ree_id)
    try:
        content = workbench_manager.read_file_bytes(handle, path)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="application/octet-stream")


@manage_ree_router.put("/api/v1/rees/{ree_id}/files/content")
def put_workspace_file_content_route(ree_id: str, payload: WorkspaceFileContentPayload):
    handle = _require_handle(ree_id)
    cmd = WriteFileCommand(args=WriteFileArgs(path=payload.path, content=payload.content))
    wb_result = _dispatch_or_500(handle, cmd, "write-file", "Workbench write_file failed")
    return wb_result.outputs or {"updatedAt": None}


@manage_ree_router.delete("/api/v1/rees/{ree_id}/files/content")
def delete_workspace_file_content_route(ree_id: str, path: str = Query(...)):
    handle = _require_handle(ree_id)
    cmd = DeleteFileCommand(args=DeleteFileArgs(path=path))
    wb_result = _dispatch_or_500(handle, cmd, "delete-file", "Workbench delete_file failed")
    return wb_result.outputs or {"deletedAt": None}


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


@manage_ree_router.post("/api/v1/rees/{ree_id}/ree:seal")
def seal_ree_route(ree_id: str, payload: ReeSealPayload):
    handle = _require_handle(ree_id)
    try:
        workspace = workbench_manager.seal(
            handle,
            source_included=payload.includeSource,
            runtime_included=payload.includeRuntime,
        )
    except WorkbenchUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return workspace


@manage_ree_router.get("/api/v1/rees/{ree_id}/ree-archive")
def download_workspace_ree_archive_route(ree_id: str):
    handle = _require_handle(ree_id)
    try:
        archive_bytes = workbench_manager.build_archive(handle)
    except RuntimeError as exc:
        detail = str(exc)
        if "not sealed" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    archive_filename = _archive_download_filename(handle)
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{archive_filename}\"; filename*=UTF-8''{quote(archive_filename)}"
            )
        },
    )


# ================================================
# Helpers
# ================================================


def _archive_download_filename(handle: WorkbenchHandle) -> str:
    metadata = workbench_manager.get_ree_metadata(handle)
    raw_name = str(metadata.get("name") or "").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    if not safe_stem:
        safe_stem = "ree"
    return f"{safe_stem}.zip"
