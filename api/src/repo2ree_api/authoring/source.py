from __future__ import annotations

from fastapi import APIRouter, Request

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    AcquireSourcePayload,
    ReeDocument,
    RunSummary,
    SourceUploadCompletePayload,
    UploadInitPayload,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.contracts.runs import runs
from repo2ree_api.control.run_orchestration import run_summary, start_single_command_run
from repo2ree_api.control.upload_runs import StagedUploadLog, start_staged_upload_run
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_api.workbench.uploads import mint_upload_token, stage_upload_bytes
from repo2ree_protocol.command import AcquireSourceArgs, AcquireSourceCommand, RemoveSourceCommand

source_router = APIRouter()


@source_router.post(
    "/api/v1/rees/{ree_id}/acquire-source",
    tags=["rees", "sources"],
    operation_id="acquireSource",
    openapi_extra=runs("acquire_source"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def acquire_source_route(ree_id: str, payload: AcquireSourcePayload) -> RunSummary:
    request_payload = {
        "mode": "download",
        "origin_url": payload.origin_url,
        "source_type": payload.source_type,
        "revision": payload.revision,
        "history": payload.history,
    }

    run_state = start_single_command_run(
        ree_id,
        action="acquire_source",
        command=AcquireSourceCommand(
            args=AcquireSourceArgs(
                mode="download",
                origin_url=payload.origin_url,
                source_type=payload.source_type,
                revision=(payload.revision or "").strip(),
                history=payload.history,
            )
        ),
        request_payload=request_payload,
        canceled_message="Source acquisition canceled",
        fallback_outputs=request_payload,
        idempotency_key=payload.idempotency_key,
    )

    return RunSummary.model_validate(run_summary(run_state))


@source_router.post(
    "/api/v1/rees/{ree_id}/source:upload-init",
    tags=["rees", "sources"],
    operation_id="initializeSourceUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def upload_init_route(ree_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    return UploadInitResponse.model_validate(
        mint_upload_token(ree_id, payload, upload_route="source:upload", purpose="source", action="upload_source")
    )


@source_router.put(
    "/api/v1/rees/{ree_id}/source:upload/{upload_token}",
    tags=["rees", "sources"],
    operation_id="uploadSourceBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_upload_bytes_route(ree_id: str, upload_token: str, request: Request) -> UploadStoredResponse:
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="source")
    )


@source_router.post(
    "/api/v1/rees/{ree_id}/source:upload-complete",
    tags=["rees", "sources"],
    operation_id="completeSourceUpload",
    openapi_extra=runs("acquire_source"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def upload_complete_route(ree_id: str, payload: SourceUploadCompletePayload) -> RunSummary:
    run_state = start_staged_upload_run(
        ree_id,
        upload_token=payload.upload_token,
        archive_name=payload.archive_name,
        purpose="source",
        action="upload_source",
        command=AcquireSourceCommand(
            args=AcquireSourceArgs(
                mode="upload",
                upload_token=payload.upload_token,
                archive_name=payload.archive_name,
            )
        ),
        request_payload={
            "mode": "upload",
            "upload_token": payload.upload_token,
            "archive_name": payload.archive_name,
        },
        messages=StagedUploadLog(
            starting=f"Starting source upload extraction for {payload.archive_name}",
            canceled="Source upload canceled",
            copied="Archive copied; extracting into the workspace",
            succeeded="Source upload extraction succeeded",
        ),
        idempotency_key=payload.idempotency_key,
    )
    return RunSummary.model_validate(run_summary(run_state))


@source_router.post(
    "/api/v1/rees/{ree_id}/remove-source",
    tags=["rees", "sources"],
    operation_id="removeSource",
    openapi_extra=runs("remove_source"),
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def remove_source_route(ree_id: str) -> ReeDocument:
    with author_api_action("remove_source", ree_id):
        handle = require_handle(ree_id)
        with ree_command_span("remove-source", ree_id):
            dispatch_or_fail(handle, RemoveSourceCommand(), "remove-source", "Workbench remove_source failed")
            return ReeDocument.of(handle.ree_id, command_dispatcher.get_ree_document(handle))
