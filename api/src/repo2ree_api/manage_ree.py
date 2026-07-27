import logging
import tempfile
import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from repo2ree_api.api_utils import keyset_paginate
from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    DeleteReeResponse,
    FileMutationResponse,
    ReeDocument,
    ReeList,
    ReeState,
    ReprovisionResponse,
    RunSummary,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree.archives import archive_download_filename, spool_chunks
from repo2ree_api.ree.uploads import (
    copy_staged_upload_into_workbench,
    mint_upload_token,
    stage_upload_bytes,
)
from repo2ree_api.ree_commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_api.run_management import (
    append_run_log,
    is_cancel_requested,
    list_runs,
    run_summary,
    start_background_run,
    start_provisioning_run,
    start_single_command_run,
    update_run_outputs,
)
from repo2ree_api.run_registry import ACTIVE_STATUSES
from repo2ree_api.schemas import (
    ReeBundleLoadPayload,
    ReeCreatePayload,
    ReeIntentPatchPayload,
    ReeIntentReplacePayload,
    ReeSealPayload,
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    UploadInitPayload,
    WorkspaceFileContentPayload,
)
from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadSizeMismatchError,
    discard_staged_upload,
    staged_upload_path,
    validate_upload_owner,
)
from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol import (
    ActionResult,
    DeleteFileCommand,
    LoadReeBundleCommand,
    PatchReeIntentCommand,
    PrepareSourceCommand,
    RemoveSourceCommand,
    SealReeCommand,
    WriteFileCommand,
)
from repo2ree_protocol.command import (
    DeleteFileArgs,
    LoadReeBundleArgs,
    PatchReeIntentArgs,
    PrepareSourceArgs,
    SealReeArgs,
    WriteFileArgs,
)

# ================================================
# Logging
# ================================================


_log = logging.getLogger(__name__)


# ================================================
# Utility Functions
# ================================================


def _content_etag(content: bytes) -> str:
    """The etag returned for a written file.

    The workbench validates a later ``if_match`` against
    ``workspace_content_etag``, which digests the stored bytes the same way —
    one shared helper so the compare cannot drift across the two processes.
    """
    return digest_bytes(content)


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
def create_workspace_route(payload: ReeCreatePayload) -> RunSummary:
    ree_id = uuid.uuid4().hex
    name = payload.name or ree_id[:8]
    # Blank/omitted image falls back to the server default in the manager.
    image = (payload.workbench_image or "").strip() or None
    # Blank/omitted agent means "any connected agent" (single-agent path).
    agent_id = (payload.agent_id or "").strip()

    # Provision in the background so the cold-machine image pull streams its
    # progress live into the run's log stream (GET .../runs/{run_id}/logs)
    # instead of blocking the request with no visible output. The ree_id is
    # minted up front, so the response carries it immediately.
    def _runner(rid: str, run_id: str) -> ActionResult:
        def _log(stream: str, level: str, message: str) -> None:
            append_run_log(rid, run_id, stream, level, message)

        if is_cancel_requested(rid, run_id):
            _log("system", "warn", "Provisioning canceled before it started")
            return ActionResult(status="canceled")

        # Note: cancel is only honoured at the phase boundaries below — the image
        # pull and container start inside provision() run to completion once
        # begun, so a cancel mid-pull only takes effect afterwards.
        try:
            handle = workbench_manager.provision(rid, name, log=_log, image=image, agent_id=agent_id)
        except Exception as exc:
            _log("system", "error", f"Workbench provisioning failed: {exc}")
            return ActionResult.failed(
                "unavailable",
                f"Workbench provisioning failed: {exc}",
                origin="supervisor",
                retryable=True,
            )

        if is_cancel_requested(rid, run_id):
            _log("system", "warn", "Provisioning canceled after workbench startup")
            return ActionResult(status="canceled", outputs={"workspace": workbench_manager.get_workspace(handle)})

        return ActionResult(status="succeeded", outputs={"workspace": workbench_manager.get_workspace(handle)})

    run_state = start_provisioning_run(
        ree_id=ree_id,
        request_payload=payload.model_dump(),
        runner=_runner,
    )
    return RunSummary.model_validate(run_summary(run_state))


@manage_ree_router.get(
    "/api/v1/rees",
    operation_id="listRees",
    response_model=ReeList,
    responses=ERROR_RESPONSES,
)
def list_workspaces_route(
    cursor: str | None = Query(None),
    limit: int | None = Query(None, ge=1),
    status: str | None = Query(None),
) -> ReeList:
    items = workbench_manager.list_all_metadata()
    if status:
        items = [m for m in items if m.get("status") == status]
    # Keyset pagination needs an immutable sort key: created_at (with ree_id as
    # the unique tiebreak), not the manager's updated_at ordering, which shifts
    # whenever an REE is touched mid-pagination.
    items.sort(key=_ree_page_key, reverse=True)
    page, next_cursor, _has_more = keyset_paginate(items, cursor=cursor, limit=limit, key=_ree_page_key)
    return ReeList.model_validate({"items": page, "next_cursor": next_cursor})


def _ree_page_key(metadata: dict[str, Any]) -> tuple[str, str]:
    return str(metadata.get("created_at", "")), str(metadata.get("ree_id", ""))


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}",
    operation_id="getRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def get_workspace_route(ree_id: str) -> ReeDocument:
    handle = require_handle(ree_id)
    workspace = workbench_manager.get_workspace(handle)
    # get-workspace runs inside the container and can't know the image, so the
    # manager (which owns the registry) supplies it.
    workspace["workbench_image"] = workbench_manager.image_for(handle)
    return ReeDocument.model_validate(workspace)


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}/state",
    operation_id="getReeState",
    response_model=ReeState,
    responses=ERROR_RESPONSES,
)
def get_workspace_state_route(ree_id: str) -> ReeState:
    """Compact automation view: durable state and file metadata, never contents."""
    handle = require_handle(ree_id)
    workspace = workbench_manager.get_workspace_state(handle)
    active_runs = [run for run in list_runs(ree_id) if run.get("status") in ACTIVE_STATUSES]
    state = {
        "ree_id": workspace["ree_id"],
        "name": workspace["name"],
        "status": workspace["status"],
        "updated_at": workspace["updated_at"],
        "workbench": {
            "status": "available",
            "agent_id": handle.agent_id,
            "image": workbench_manager.image_for(handle),
        },
        "ree_intent": workspace.get("ree_intent", {}),
        "ree_session": workspace.get("ree_session", {}),
        "consistency": workspace.get("consistency", {}),
        "author_receipts": workspace.get("author_receipts", {}),
        "ree_steps": workspace.get("ree_steps", []),
        "files": workspace.get("files", []),
        "ree_files": workspace.get("ree_files", []),
        "active_runs": active_runs,
    }
    if "source_repo" in workspace:
        state["source_repo"] = workspace["source_repo"]
    return ReeState.model_validate(state)


@manage_ree_router.patch(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="patchReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def patch_ree_intent_route(ree_id: str, payload: ReeIntentPatchPayload) -> ReeDocument:
    handle = require_handle(ree_id)
    with ree_command_span("patch-intent", ree_id):
        cmd = PatchReeIntentCommand(
            args=PatchReeIntentArgs(
                patch=payload.ree_intent_patch.model_dump(mode="json", exclude_unset=True),
                expected_version=payload.expected_version or "",
            )
        )
        dispatch_or_fail(handle, cmd, "patch-intent", "Workbench patch_ree_intent failed")
        return ReeDocument.model_validate(workbench_manager.get_workspace(handle))


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="replaceReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def replace_ree_intent_route(ree_id: str, payload: ReeIntentReplacePayload) -> ReeDocument:
    """Atomically replace the complete typed authoring intent.

    Delegating to the patch route is a true replace only because the patch is
    re-validated from a full model_dump() — every ReeIntent field (defaults
    included) counts as explicitly set, so the patch dispatch's exclude_unset
    keeps them all and apply_patch overwrites each top-level key. Guarded by
    test_replace_intent_resets_fields_omitted_from_the_new_intent.
    """
    return patch_ree_intent_route(
        ree_id,
        ReeIntentPatchPayload(
            ree_intent_patch=ReeIntent.model_validate(payload.ree_intent.model_dump(mode="json")),
            expected_version=payload.expected_version,
        ),
    )


@manage_ree_router.delete(
    "/api/v1/rees/{ree_id}",
    operation_id="deleteRee",
    response_model=DeleteReeResponse,
    responses=ERROR_RESPONSES,
)
def delete_workspace_route(ree_id: str) -> DeleteReeResponse:
    handle = require_handle(ree_id)
    with ree_command_span("delete", ree_id):
        try:
            workbench_manager.teardown(handle)
        except Exception as exc:
            _log.warning("workbench teardown failed for %s: %s", ree_id, exc)
            raise HTTPException(status_code=500, detail=f"Workbench teardown failed: {exc}") from exc
        return DeleteReeResponse.model_validate(
            {
                "deleted_at": utc_now(),
                "state": "deleted",
            }
        )


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:acquire",
    tags=["sources"],
    operation_id="startSourceAcquisition",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def acquire_source_route(ree_id: str, payload: SourceAcquirePayload) -> RunSummary:
    request_payload = {
        "mode": "download",
        "origin_url": payload.origin_url,
        "source_type": payload.source_type,
        "revision": payload.revision,
    }

    run_state = start_single_command_run(
        ree_id,
        operation="source",
        command=PrepareSourceCommand(
            args=PrepareSourceArgs(
                mode="download",
                origin_url=payload.origin_url,
                source_type=payload.source_type,
                revision=(payload.revision or "").strip(),
            )
        ),
        request_payload=request_payload,
        run_id_prefix="source",
        canceled_message="Source acquisition canceled",
        fallback_outputs=request_payload,
        idempotency_key=payload.idempotency_key,
    )

    return RunSummary.model_validate(run_summary(run_state))


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:upload-init",
    tags=["sources"],
    operation_id="initializeSourceUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def upload_init_route(ree_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    return UploadInitResponse.model_validate(
        mint_upload_token(ree_id, payload, upload_route="source:upload", purpose="source")
    )


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/source:upload/{upload_token}",
    tags=["sources"],
    operation_id="uploadSourceBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_upload_bytes_route(ree_id: str, upload_token: str, request: Request) -> UploadStoredResponse:
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="source")
    )


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/source:upload-complete",
    tags=["sources"],
    operation_id="completeSourceUpload",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def upload_complete_route(ree_id: str, payload: SourceUploadCompletePayload) -> RunSummary:
    handle = require_handle(ree_id)
    request_payload = {
        "mode": "upload",
        "upload_token": payload.upload_token,
        "archive_name": payload.archive_name,
    }
    try:
        validate_upload_owner(
            payload.upload_token,
            ree_id=ree_id,
            purpose="source",
            file_name=payload.archive_name,
        )
        staged_host = staged_upload_path(payload.upload_token)
    except (InvalidUploadTokenError, UploadSizeMismatchError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownUploadTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _runner(ws_id: str, run_id: str) -> ActionResult:
        def _log_run(stream: str, level: str, message: str) -> None:
            append_run_log(ws_id, run_id, stream, level, message)

        _log_run(
            "system",
            "info",
            f"Starting source upload extraction for {payload.archive_name}",
        )
        if is_cancel_requested(ws_id, run_id):
            _log_run("system", "warn", "Source upload canceled")
            return ActionResult(status="canceled", outputs=request_payload)

        copy_failure = copy_staged_upload_into_workbench(
            handle,
            payload.upload_token,
            staged_host,
            log_run=_log_run,
            outputs=request_payload,
        )
        if copy_failure is not None:
            return copy_failure
        _log_run("system", "info", "Archive copied; extracting into the workspace")

        try:
            result = workbench_manager.dispatch_action(
                handle,
                PrepareSourceCommand(
                    args=PrepareSourceArgs(
                        mode="upload",
                        upload_token=payload.upload_token,
                        archive_name=payload.archive_name,
                    )
                ),
                run_id,
                _log_run,
            )
        finally:
            # Ownership transferred to the workbench; always reclaim the host copy.
            discard_staged_upload(payload.upload_token)

        if result.status == "succeeded":
            _log_run("system", "info", "Source upload extraction succeeded")
            return ActionResult(status="succeeded", outputs=request_payload)
        return result.model_copy(update={"outputs": request_payload})

    run_state = start_background_run(
        ree_id=ree_id,
        operation="source",
        request_payload=request_payload,
        run_id_prefix="source",
        runner=_runner,
        idempotency_key=payload.idempotency_key,
    )

    return RunSummary.model_validate(run_summary(run_state))


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/ree:upload-init",
    operation_id="initializeReeBundleUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def bundle_upload_init_route(ree_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    """Open a staging slot for a downloaded REE bundle (see ``ree:load``)."""
    return UploadInitResponse.model_validate(
        mint_upload_token(ree_id, payload, upload_route="ree:upload", purpose="bundle")
    )


@manage_ree_router.put(
    "/api/v1/rees/{ree_id}/ree:upload/{upload_token}",
    operation_id="uploadReeBundleBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_bundle_bytes_route(ree_id: str, upload_token: str, request: Request) -> UploadStoredResponse:
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="bundle")
    )


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/ree:load",
    operation_id="loadReeBundle",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def load_ree_bundle_route(ree_id: str, payload: ReeBundleLoadPayload) -> RunSummary:
    """Make this REE be the uploaded bundle: intent, source, evidence, and all.

    The counterpart of ``ree-archive``. Intended right after ``createRee`` —
    loading replaces whatever the REE holds, so a fresh workbench is the only
    place it is non-destructive.
    """
    handle = require_handle(ree_id)
    request_payload = {"upload_token": payload.upload_token, "archive_name": payload.archive_name}
    try:
        validate_upload_owner(
            payload.upload_token,
            ree_id=ree_id,
            purpose="bundle",
            file_name=payload.archive_name,
        )
        staged_host = staged_upload_path(payload.upload_token)
    except (InvalidUploadTokenError, UploadSizeMismatchError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnknownUploadTokenError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _runner(ws_id: str, run_id: str) -> ActionResult:
        def _log_run(stream: str, level: str, message: str) -> None:
            append_run_log(ws_id, run_id, stream, level, message)

        _log_run("system", "info", f"Loading REE bundle {payload.archive_name}")
        if is_cancel_requested(ws_id, run_id):
            _log_run("system", "warn", "REE bundle load canceled")
            return ActionResult(status="canceled", outputs=request_payload)

        copy_failure = copy_staged_upload_into_workbench(
            handle,
            payload.upload_token,
            staged_host,
            log_run=_log_run,
            outputs=request_payload,
        )
        if copy_failure is not None:
            return copy_failure
        _log_run("system", "info", "Bundle copied; restoring it into the REE")

        command = LoadReeBundleCommand(
            args=LoadReeBundleArgs(
                upload_token=payload.upload_token,
                archive_name=payload.archive_name,
            )
        )
        try:
            result = workbench_manager.dispatch_action(handle, command, run_id, _log_run)
            if result.outputs:
                update_run_outputs(ws_id, run_id, result.outputs)
        finally:
            # Ownership transferred to the workbench; always reclaim the host copy.
            discard_staged_upload(payload.upload_token)

        if result.status != "succeeded":
            _log_run("system", "error", f"Workbench step load_ree_bundle {result.status}")
            return result
        _log_run("system", "info", "REE bundle load succeeded")
        return ActionResult(status="succeeded", outputs={**request_payload, **(result.outputs or {})})

    run_state = start_background_run(
        ree_id=ree_id,
        operation="ree-load",
        request_payload=request_payload,
        run_id_prefix="ree-load",
        runner=_runner,
        idempotency_key=payload.idempotency_key,
    )

    return RunSummary.model_validate(run_summary(run_state))


@manage_ree_router.delete(
    "/api/v1/rees/{ree_id}/source",
    tags=["sources"],
    operation_id="removeSource",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def remove_source_route(ree_id: str) -> ReeDocument:
    handle = require_handle(ree_id)
    with ree_command_span("remove-source", ree_id):
        dispatch_or_fail(handle, RemoveSourceCommand(), "remove-source", "Workbench remove_source failed")
        return ReeDocument.model_validate(workbench_manager.get_workspace(handle))


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
def get_workspace_file_raw_route(ree_id: str, path: str = Query(...)) -> Response:
    handle = require_handle(ree_id)
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
def put_workspace_file_content_route(ree_id: str, payload: WorkspaceFileContentPayload) -> FileMutationResponse:
    handle = require_handle(ree_id)
    with ree_command_span("write-file", ree_id):
        # The if_match check rides inside the command so the workbench verifies
        # it under the same per-REE serialization as the write — an API-side
        # pre-read could pass and still lose to a concurrent writer.
        cmd = WriteFileCommand(
            args=WriteFileArgs(path=payload.path, content=payload.content, expected_etag=payload.if_match or "")
        )
        wb_result = dispatch_or_fail(handle, cmd, "write-file", "Workbench write_file failed")
        result = dict(wb_result.outputs or {})
        result["etag"] = _content_etag(payload.content.encode())
        result.setdefault("updated_at", None)
        return FileMutationResponse.model_validate(result)


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
    if_match: str | None = Query(None),
) -> FileMutationResponse:
    handle = require_handle(ree_id)
    with ree_command_span("delete-file", ree_id):
        cmd = DeleteFileCommand(args=DeleteFileArgs(path=path, expected_etag=if_match or ""))
        wb_result = dispatch_or_fail(handle, cmd, "delete-file", "Workbench delete_file failed")
        return FileMutationResponse.model_validate(wb_result.outputs or {"deleted_at": None})


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/workbench/reprovision",
    operation_id="reprovisionWorkbench",
    response_model=ReprovisionResponse,
    responses=ERROR_RESPONSES,
)
def reprovision_workbench_route(ree_id: str) -> ReprovisionResponse:
    """Replace the workbench container from the current image, keeping REE volume data."""
    try:
        workbench_manager.reprovision(ree_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "reprovision_failed",
                "message": f"Workbench reprovision failed: {exc}",
                "details": None,
                # A fresh container start can fail transiently (image pull,
                # agent hiccup); retrying the reprovision is safe.
                "retryable": True,
            },
        ) from exc
    return ReprovisionResponse.model_validate({"status": "reprovisioned", "ree_id": ree_id})


@manage_ree_router.post(
    "/api/v1/rees/{ree_id}/ree:seal",
    operation_id="sealRee",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def seal_ree_route(ree_id: str, payload: ReeSealPayload) -> ReeDocument:
    handle = require_handle(ree_id)
    with ree_command_span("seal", ree_id):
        cmd = SealReeCommand(
            args=SealReeArgs(
                source_included=payload.include_source,
                runtime_included=payload.include_runtime,
                results_included=payload.include_results,
            )
        )
        dispatch_or_fail(handle, cmd, "seal", "Workbench seal_ree failed")
        # Return the post-seal workspace so the client sees the sealed state.
        return ReeDocument.model_validate(workbench_manager.get_workspace(handle))


@manage_ree_router.get(
    "/api/v1/rees/{ree_id}/ree-archive",
    operation_id="downloadReeArchive",
    response_class=StreamingResponse,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "REE ZIP bundle — the sealed archive, or a draft bundle when unsealed",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def download_workspace_ree_archive_route(ree_id: str) -> StreamingResponse:
    """Download this REE as a bundle, loadable into another REE via ``ree:load``.

    A sealed REE hands back its immutable sealed archive; an unsealed one is
    assembled into a draft bundle on demand. Only the sealed bundle carries a
    seal hash — a draft is a handoff, not a citable artifact.
    """
    handle = require_handle(ree_id)
    archive_filename = archive_download_filename(handle)
    # Spool the archive to a control-plane temp file before responding. The
    # per-REE lock (and the agent's exec) is held only while the workbench
    # streams to us — never for as long as the client takes to download — so a
    # slow client cannot block other operations on the REE.
    spool = tempfile.TemporaryFile()
    try:
        with ree_command_span("ree-archive", ree_id):
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BaseException:
        spool.close()
        raise
    return StreamingResponse(
        spool_chunks(spool),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{archive_filename}\"; filename*=UTF-8''{quote(archive_filename)}"
            ),
            "Content-Length": str(size),
        },
    )
