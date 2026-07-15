import asyncio
import hashlib
import logging
import re
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from repo2ree_api.api_utils import paginate
from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    DeleteReeResponse,
    FileMutationResponse,
    ReeDocument,
    ReeList,
    ReeState,
    RemoveSourceResponse,
    ReprovisionResponse,
    RunSummary,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.run_management import (
    _append_run_log,
    _is_cancel_requested,
    _list_runs,
    _run_summary,
    _start_background_run,
    _start_provisioning_run,
    _update_run_outputs,
)
from repo2ree_api.run_registry import ACTIVE_STATUSES
from repo2ree_api.schemas import (
    ReeCreatePayload,
    ReeIntentPatchPayload,
    ReeIntentReplacePayload,
    ReeSealPayload,
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    UploadInitPayload,
    WorkspaceFileContentPayload,
)
from repo2ree_api.settings import service_settings
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    UploadStagingFullError,
    UploadTooLargeError,
    discard_expired_uploads,
    discard_staged_upload,
    new_upload_token,
    stage_upload_stream,
    staged_upload_path,
)
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol import (
    AcquireSourceCommand,
    ActionResult,
    DeleteFileCommand,
    ExtractUploadCommand,
    MaterializeWorkspaceCommand,
    PatchReeIntentCommand,
    RemoveSourceCommand,
    ResetForSourceChangeCommand,
    SealReeCommand,
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
    SealReeArgs,
    UpdateSourceMetadataArgs,
    WriteFileArgs,
)
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    command_metric_attrs,
    get_meter,
    get_tracer,
    record_command_status,
)
from repo2ree_supervisor import WorkbenchHandle, WorkbenchUnavailableError

# ================================================
# Logging
# ================================================


_log = logging.getLogger(__name__)


# ================================================
# Observability
# ================================================


_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_command_counter = _meter.create_counter(
    "ree.command",
    description="Number of synchronous REE commands handled, by operation and status.",
)
_command_duration = _meter.create_histogram(
    "ree.command_duration_seconds",
    description="Wall-clock duration of a synchronous REE command handler.",
    unit="s",
)


@contextmanager
def _ree_command_span(operation: str, ree_id: str) -> Iterator[None]:
    """Operation-level span + metrics for a synchronous REE command handler.

    Mirrors the ``run.{operation}`` root that background runs get in the run
    registry: every synchronous main command gets its own ``ree.{operation}``
    span tagged with the REE and a terminal status, plus a duration histogram
    and count, so traces and error-rate queries treat synchronous and
    background commands uniformly. The inner ``workbench.dispatch_action`` span
    nests beneath this one.

    Wrap only the command work — call ``_require_handle`` first so a 404/503 for
    an unknown or unreachable REE stays out of the command's status and metrics.
    """
    t0 = time.monotonic()
    status = "succeeded"
    with _tracer.start_as_current_span(f"ree.{operation}") as span:
        CommandSpanAttrs(operation=operation, ree_id=ree_id).apply(span)
        try:
            yield
        except Exception as exc:
            status = "failed"
            span.record_exception(exc)
            raise
        finally:
            record_command_status(span, status)
            attrs = command_metric_attrs(operation, status=status)
            _command_duration.record(time.monotonic() - t0, attrs)
            _command_counter.add(1, attrs)


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


def _content_etag(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _require_file_match(handle: WorkbenchHandle, path: str, expected: str | None) -> str | None:
    """Validate an optional file content token and return the current token."""
    if not expected:
        return None
    try:
        actual = _content_etag(workbench_manager.read_file_bytes(handle, path))
    except WorkbenchUnavailableError:
        raise
    except RuntimeError:
        actual = None
    if expected != actual:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "message": "Workspace file changed since it was read",
                "details": {"path": path, "expectedVersion": expected, "actualVersion": actual},
                "retryable": True,
            },
        )
    return actual


def _download_pipeline(lead: AcquireSourceCommand, metadata_args: UpdateSourceMetadataArgs) -> list[Command]:
    """Download: acquire (fetch into upstream) → snapshot → materialize → update-metadata.

    A downloaded source is *fetched then frozen*: acquire populates upstream, then
    snapshot captures it.
    """
    return [
        ResetForSourceChangeCommand(),
        lead,
        SnapshotUpstreamCommand(),
        MaterializeWorkspaceCommand(),
        UpdateSourceMetadataCommand(args=metadata_args),
    ]


def _upload_pipeline(lead: ExtractUploadCommand, metadata_args: UpdateSourceMetadataArgs) -> list[Command]:
    """Upload: extract-upload (→ snapshot) → acquire (extract) → materialize → update-metadata.

    An upload has no origin, so it is *born frozen*: the upload ingest produces
    the snapshot, then the unified acquire extracts it into upstream — the same
    extract arm a reproducer uses. No separate snapshot step.
    """
    return [
        ResetForSourceChangeCommand(),
        lead,
        AcquireSourceCommand(args=AcquireSourceArgs()),
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


# ================================================
# Router
# ================================================


manage_ree_router = APIRouter(tags=["rees"])


# ================================================
# Route Handlers
# ================================================


@manage_ree_router.post(
    "/api/v1/rees",
    operation_id="createRee",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_workspace_route(payload: ReeCreatePayload):
    ree_id = uuid.uuid4().hex
    name = payload.name or ree_id[:8]
    # Blank/omitted image falls back to the server default in the manager.
    image = (payload.workbenchImage or "").strip() or None
    # Blank/omitted agent means "any connected agent" (single-agent path).
    agent_id = (payload.agentId or "").strip()

    # Provision in the background so the cold-machine image pull streams its
    # progress live into the run's log stream (GET .../runs/{run_id}/logs)
    # instead of blocking the request with no visible output. The reeId is
    # minted up front, so the response carries it immediately.
    def _runner(rid: str, run_id: str) -> tuple[str, dict[str, Any]]:
        def _log(stream: str, level: str, message: str) -> None:
            _append_run_log(rid, run_id, stream, level, message)

        if _is_cancel_requested(rid, run_id):
            _log("system", "warn", "Provisioning canceled before it started")
            return "canceled", {}

        # Note: cancel is only honoured at the phase boundaries below — the image
        # pull and container start inside provision() run to completion once
        # begun, so a cancel mid-pull only takes effect afterwards.
        try:
            handle = workbench_manager.provision(rid, name, log=_log, image=image, agent_id=agent_id)
        except Exception as exc:
            _log("system", "error", f"Workbench provisioning failed: {exc}")
            return "failed", {}

        if _is_cancel_requested(rid, run_id):
            _log("system", "warn", "Provisioning canceled after workbench startup")
            return "canceled", {"workspace": workbench_manager.get_workspace(handle)}

        return "succeeded", {"workspace": workbench_manager.get_workspace(handle)}

    run_state = _start_provisioning_run(
        ree_id=ree_id,
        request_payload=payload.model_dump(),
        runner=_runner,
    )
    return _run_summary(run_state)


@manage_ree_router.get(
    "/api/v1/rees",
    operation_id="listRees",
    response_model=ReeList,
    responses=ERROR_RESPONSES,
)
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


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}",
    operation_id="getRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def get_workspace_route(ree_id: str):
    handle = _require_handle(ree_id)
    workspace = workbench_manager.get_workspace(handle)
    # get-workspace runs inside the container and can't know the image, so the
    # manager (which owns the registry) supplies it.
    workspace["workbenchImage"] = workbench_manager.image_for(handle)
    return workspace


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}/state",
    operation_id="getReeState",
    response_model=ReeState,
    responses=ERROR_RESPONSES,
)
def get_workspace_state_route(ree_id: str):
    """Compact automation view: durable state and file metadata, never contents."""
    handle = _require_handle(ree_id)
    workspace = workbench_manager.get_workspace_state(handle)
    active_runs = [run for run in _list_runs(ree_id) if run.get("status") in ACTIVE_STATUSES]
    state = {
        "reeId": workspace["reeId"],
        "name": workspace["name"],
        "status": workspace["status"],
        "updatedAt": workspace["updatedAt"],
        "workbench": {
            "status": "available",
            "agentId": handle.agent_id,
            "image": workbench_manager.image_for(handle),
        },
        "reeIntent": workspace.get("reeIntent", {}),
        "reeSession": workspace.get("reeSession", {}),
        "consistency": workspace.get("consistency", {}),
        "files": workspace.get("files", []),
        "activeRuns": active_runs,
    }
    for key in ("source", "sourceRepo"):
        if key in workspace:
            state[key] = workspace[key]
    return state


@manage_ree_router.patch(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="patchReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def patch_ree_intent_route(ree_id: str, payload: ReeIntentPatchPayload):
    handle = _require_handle(ree_id)
    with _ree_command_span("patch-intent", ree_id):
        current = workbench_manager.get_ree_metadata(handle)
        if payload.expectedVersion and payload.expectedVersion != current.get("updatedAt"):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "version_conflict",
                    "message": "REE intent changed since it was read",
                    "details": {
                        "expectedVersion": payload.expectedVersion,
                        "actualVersion": current.get("updatedAt"),
                    },
                    "retryable": True,
                },
            )

        cmd = PatchReeIntentCommand(args=PatchReeIntentArgs(patch=dict(payload.reeIntentPatch or {})))
        _dispatch_or_500(handle, cmd, "patch-intent", "Workbench patch_ree_intent failed")
        return workbench_manager.get_workspace(handle)


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="replaceReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def replace_ree_intent_route(ree_id: str, payload: ReeIntentReplacePayload):
    """Atomically replace the complete typed authoring intent."""
    return patch_ree_intent_route(
        ree_id,
        ReeIntentPatchPayload(
            reeIntentPatch=payload.reeIntent.model_dump(mode="json"),
            expectedVersion=payload.expectedVersion,
        ),
    )


@manage_ree_router.delete(
    "/api/v1/rees/{ree_id}",
    operation_id="deleteRee",
    response_model=DeleteReeResponse,
    responses=ERROR_RESPONSES,
)
def delete_workspace_route(ree_id: str):
    handle = _require_handle(ree_id)
    with _ree_command_span("delete", ree_id):
        try:
            workbench_manager.teardown(handle)
        except Exception as exc:
            _log.warning("workbench teardown failed for %s: %s", ree_id, exc)
            raise HTTPException(status_code=500, detail=f"Workbench teardown failed: {exc}") from exc
        return {
            "deletedAt": utc_now(),
            "state": "deleted",
        }


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:acquire",
    tags=["sources"],
    operation_id="startSourceAcquisition",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def acquire_source_route(ree_id: str, payload: SourceAcquirePayload):
    handle = _require_handle(ree_id)
    request_payload = {
        "mode": "download",
        "originUrl": payload.originUrl,
        "sourceType": payload.sourceType,
        "revision": payload.revision,
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

        pipeline = _download_pipeline(
            AcquireSourceCommand(
                args=AcquireSourceArgs(
                    origin_url=payload.originUrl,
                    source_type=payload.sourceType,  # type: ignore[arg-type]
                    revision=(payload.revision or "").strip(),
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
        idempotency_key=payload.idempotencyKey,
    )

    return _run_summary(run_state)


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:upload-init",
    tags=["sources"],
    operation_id="initializeSourceUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def upload_init_route(ree_id: str, payload: UploadInitPayload):
    _require_handle(ree_id)
    if payload.size > service_settings.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "upload_too_large",
                "message": f"Upload exceeds the {service_settings.UPLOAD_MAX_BYTES}-byte limit",
                "details": {"declaredSize": payload.size, "maxBytes": service_settings.UPLOAD_MAX_BYTES},
            },
        )
    result = new_upload_token(
        file_name=payload.fileName,
        expected_size=payload.size,
        content_type=payload.contentType,
    )
    token = result["uploadToken"]
    result["uploadUrl"] = f"/api/v1/rees/{ree_id}/source:upload/{token}"
    return result


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/source:upload/{upload_token}",
    tags=["sources"],
    operation_id="uploadSourceBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_upload_bytes_route(ree_id: str, upload_token: str, request: Request):
    # This route is async to consume the HTTP request body incrementally. It runs
    # on the event loop, so blocking control-plane calls must hop to a thread:
    # ``_require_handle`` does a synchronous round-trip to the workbench agent
    # over the multiplexed WebSocket that *this same loop* pumps — calling it
    # inline deadlocks the loop against its own reply (frozen API, agent
    # keepalive death) rather than merely stalling.
    await asyncio.to_thread(_require_handle, ree_id)
    try:
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
    return {
        "uploadToken": upload_token,
        "storedAt": utc_now(),
    }


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:upload-complete",
    tags=["sources"],
    operation_id="completeSourceUpload",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def upload_complete_route(ree_id: str, payload: SourceUploadCompletePayload):
    handle = _require_handle(ree_id)
    request_payload = {
        "mode": "upload",
        "uploadToken": payload.uploadToken,
        "archiveName": payload.archiveName,
    }
    try:
        staged_host = staged_upload_path(payload.uploadToken)
    except InvalidUploadTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

        # Sweep first so a staged file past its TTL reads as expired, not found.
        # Size zero means the token was minted but the bytes never PUT.
        discard_expired_uploads()
        if not staged_host.exists() or staged_host.stat().st_size == 0:
            _log_run("system", "error", "Staged upload not found, empty, or expired")
            return "failed", request_payload

        size = staged_host.stat().st_size
        _log_run("system", "info", f"Copying staged archive into the workbench ({size} bytes)")
        try:
            workbench_manager.copy_to_workbench(
                handle,
                str(staged_host),
                f"/ree/upload-staging/{payload.uploadToken}.bin",
            )
        except Exception as exc:
            _log_run("system", "error", f"Copy to workbench failed: {exc}")
            return "failed", request_payload
        _log_run("system", "info", "Archive copied; extracting into the workspace")

        pipeline = _upload_pipeline(
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
        idempotency_key=payload.idempotencyKey,
    )

    return _run_summary(run_state)


@manage_ree_router.delete(
    "/api/v1/rees/{ree_id}/source",
    tags=["sources"],
    operation_id="removeSource",
    response_model=RemoveSourceResponse,
    responses=ERROR_RESPONSES,
)
def remove_source_route(ree_id: str):
    handle = _require_handle(ree_id)
    with _ree_command_span("remove-source", ree_id):
        _dispatch_or_500(handle, RemoveSourceCommand(), "remove-source", "Workbench remove_source failed")
        return {"workspace": workbench_manager.get_workspace(handle)}


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}/files/raw",
    tags=["files"],
    operation_id="readReeFile",
    response_class=Response,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Raw workspace file bytes",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def get_workspace_file_raw_route(ree_id: str, path: str = Query(...)):
    handle = _require_handle(ree_id)
    try:
        content = workbench_manager.read_file_bytes(handle, path)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="application/octet-stream")


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/files/content",
    tags=["files"],
    operation_id="writeReeFile",
    response_model=FileMutationResponse,
    responses=ERROR_RESPONSES,
)
def put_workspace_file_content_route(ree_id: str, payload: WorkspaceFileContentPayload):
    handle = _require_handle(ree_id)
    with _ree_command_span("write-file", ree_id):
        _require_file_match(handle, payload.path, payload.ifMatch)
        cmd = WriteFileCommand(args=WriteFileArgs(path=payload.path, content=payload.content))
        wb_result = _dispatch_or_500(handle, cmd, "write-file", "Workbench write_file failed")
        result = dict(wb_result.outputs or {})
        result["etag"] = _content_etag(payload.content.encode())
        result.setdefault("updatedAt", None)
        return result


@manage_ree_router.delete(
    "/api/v1/rees/{ree_id}/files/content",
    tags=["files"],
    operation_id="deleteReeFile",
    response_model=FileMutationResponse,
    responses=ERROR_RESPONSES,
)
def delete_workspace_file_content_route(
    ree_id: str,
    path: str = Query(...),
    if_match: str | None = Query(None, alias="ifMatch"),
):
    handle = _require_handle(ree_id)
    with _ree_command_span("delete-file", ree_id):
        _require_file_match(handle, path, if_match)
        cmd = DeleteFileCommand(args=DeleteFileArgs(path=path))
        wb_result = _dispatch_or_500(handle, cmd, "delete-file", "Workbench delete_file failed")
        return wb_result.outputs or {"deletedAt": None}


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/workbench/reprovision",
    operation_id="reprovisionWorkbench",
    response_model=ReprovisionResponse,
    responses=ERROR_RESPONSES,
)
def reprovision_workbench_route(ree_id: str):
    """Replace the workbench container from the current image, keeping REE volume data."""
    try:
        workbench_manager.reprovision(ree_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "reprovisioned", "reeId": ree_id}


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/ree:seal",
    operation_id="sealRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def seal_ree_route(ree_id: str, payload: ReeSealPayload):
    handle = _require_handle(ree_id)
    with _ree_command_span("seal", ree_id):
        cmd = SealReeCommand(
            args=SealReeArgs(
                source_included=payload.includeSource,
                runtime_included=payload.includeRuntime,
                results_included=payload.includeResults,
            )
        )
        _dispatch_or_500(handle, cmd, "seal", "Workbench seal_ree failed")
        # Return the post-seal workspace so the client sees the sealed state.
        return workbench_manager.get_workspace(handle)


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}/ree-archive",
    operation_id="downloadReeArchive",
    response_class=StreamingResponse,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Sealed REE ZIP archive",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def download_workspace_ree_archive_route(ree_id: str):
    handle = _require_handle(ree_id)
    archive_filename = _archive_download_filename(handle)
    # Spool the archive to a control-plane temp file before responding. The
    # per-REE lock (and the agent's exec) is held only while the workbench
    # streams to us — never for as long as the client takes to download — so a
    # slow client cannot block other operations on the REE.
    spool = tempfile.TemporaryFile()
    try:
        with _ree_command_span("ree-archive", ree_id):
            for chunk in workbench_manager.build_archive_stream(handle):
                spool.write(chunk)
            if spool.tell() == 0:
                raise HTTPException(status_code=502, detail="workbench returned an empty archive")
        size = spool.tell()
        spool.seek(0)
    except HTTPException:
        spool.close()
        raise
    except RuntimeError as exc:
        spool.close()
        detail = str(exc)
        if "not sealed" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except BaseException:
        spool.close()
        raise
    return StreamingResponse(
        _spool_chunks(spool),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{archive_filename}\"; filename*=UTF-8''{quote(archive_filename)}"
            ),
            "Content-Length": str(size),
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


def _spool_chunks(spool: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := spool.read(64 * 1024):
            yield chunk
    finally:
        spool.close()
