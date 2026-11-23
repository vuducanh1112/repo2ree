from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    LoadReeBundlePayload,
    RunSummary,
    SealReePayload,
    SignReePayload,
    UploadInitPayload,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.contracts.runs import runs
from repo2ree_api.control.behaviour import journal_positions, record_archive
from repo2ree_api.control.run_orchestration import run_summary, start_single_command_run
from repo2ree_api.control.upload_runs import StagedUploadLog, start_staged_upload_run
from repo2ree_api.deps import command_dispatcher, ree_index
from repo2ree_api.ree_index import entry_from_ree
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.archives import archive_download_filename, spool_chunks
from repo2ree_api.workbench.commands import ree_command_span, require_handle
from repo2ree_api.workbench.uploads import mint_upload_token, stage_upload_bytes
from repo2ree_protocol.command import (
    LoadReeBundleArgs,
    LoadReeBundleCommand,
    SealReeArgs,
    SealReeCommand,
    SignReeArgs,
    SignReeCommand,
)
from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import ReeRoute, WorkbenchUnavailableError

_log = logging.getLogger(__name__)

seal_router = APIRouter(tags=["rees"])


@seal_router.post(
    "/api/v1/rees/{ree_id}/ree:upload-init",
    operation_id="initializeReeBundleUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def bundle_upload_init_route(ree_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    return UploadInitResponse.model_validate(
        mint_upload_token(ree_id, payload, upload_route="ree:upload", purpose="bundle", action="load_ree_bundle")
    )


@seal_router.put(
    "/api/v1/rees/{ree_id}/ree:upload/{upload_token}",
    operation_id="uploadReeBundleBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_bundle_bytes_route(ree_id: str, upload_token: str, request: Request) -> UploadStoredResponse:
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="bundle")
    )


@seal_router.post(
    "/api/v1/rees/{ree_id}/load-ree-bundle",
    operation_id="loadReeBundle",
    openapi_extra=runs("load_ree_bundle"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def load_ree_bundle_route(ree_id: str, payload: LoadReeBundlePayload) -> RunSummary:
    run_state = start_staged_upload_run(
        ree_id,
        upload_token=payload.upload_token,
        archive_name=payload.archive_name,
        purpose="bundle",
        action="load_ree_bundle",
        command=LoadReeBundleCommand(
            args=LoadReeBundleArgs(
                upload_token=payload.upload_token,
                archive_name=payload.archive_name,
            )
        ),
        request_payload={"upload_token": payload.upload_token, "archive_name": payload.archive_name},
        messages=StagedUploadLog(
            starting=f"Loading REE bundle {payload.archive_name}",
            canceled="REE bundle load canceled",
            copied="Bundle copied; restoring it into the REE",
            succeeded="REE bundle load succeeded",
        ),
        idempotency_key=payload.idempotency_key,
    )
    return RunSummary.model_validate(run_summary(run_state))


@seal_router.post(
    "/api/v1/rees/{ree_id}/seal-ree",
    operation_id="sealRee",
    openapi_extra=runs("seal_ree"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def seal_ree_route(ree_id: str, payload: SealReePayload) -> RunSummary:
    def record_sealed_ree(handle: ReeRoute, result: ActionResult) -> ActionResult:
        document = command_dispatcher.get_ree_document(handle)
        _record_in_ree_index(ree_id, document)
        return result

    run_state = start_single_command_run(
        ree_id,
        action="seal_ree",
        command=SealReeCommand(
            args=SealReeArgs(
                source_included=payload.include_source,
                experiment_environment_included=payload.include_experiment_environment,
                results_included=payload.include_results,
            )
        ),
        request_payload=payload.model_dump(),
        canceled_message="REE sealing canceled",
        after_success=record_sealed_ree,
    )
    return RunSummary.model_validate(run_summary(run_state))


@seal_router.post(
    "/api/v1/rees/{ree_id}/signature:upload-init",
    operation_id="initializeSignatureUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def signature_upload_init_route(ree_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    return UploadInitResponse.model_validate(
        mint_upload_token(ree_id, payload, upload_route="signature:upload", purpose="signature", action="sign_ree")
    )


@seal_router.put(
    "/api/v1/rees/{ree_id}/signature:upload/{upload_token}",
    operation_id="uploadSignatureBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_signature_bytes_route(ree_id: str, upload_token: str, request: Request) -> UploadStoredResponse:
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="signature")
    )


@seal_router.post(
    "/api/v1/rees/{ree_id}/sign-ree",
    operation_id="signRee",
    openapi_extra=runs("sign_ree"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def sign_ree_route(ree_id: str, payload: SignReePayload) -> RunSummary:
    run_state = start_staged_upload_run(
        ree_id,
        upload_token=payload.upload_token,
        archive_name=payload.archive_name,
        purpose="signature",
        action="sign_ree",
        command=SignReeCommand(
            args=SignReeArgs(claim=payload.claim, upload_token=payload.upload_token, archive_name=payload.archive_name)
        ),
        request_payload={
            "claim": payload.claim,
            "upload_token": payload.upload_token,
            "archive_name": payload.archive_name,
        },
        messages=StagedUploadLog(
            starting=f"Signing the REE with {payload.archive_name}",
            canceled="REE signing canceled",
            copied="Signature copied; adding it to the REE",
            succeeded="REE signed",
        ),
        idempotency_key=payload.idempotency_key,
    )
    return RunSummary.model_validate(run_summary(run_state))


def _record_in_ree_index(ree_id: str, document: WorkbenchReeDocument) -> None:
    try:
        ree_index.record_seal(entry_from_ree(document.ree))
    except Exception:  # noqa: BLE001
        _log.exception("REE %s sealed but could not be recorded in the index; re-seal to repair", ree_id)


@seal_router.get(
    "/api/v1/rees/{ree_id}/ree-archive",
    operation_id="downloadReeArchive",
    response_class=StreamingResponse,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "REE repository ZIP containing Git histories and selected offline LFS payloads",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def download_ree_archive_route(ree_id: str) -> StreamingResponse:
    with author_api_action("download_ree", ree_id):
        return _download_ree_archive(ree_id)


def _download_ree_archive(ree_id: str) -> StreamingResponse:
    handle = require_handle(ree_id)
    archive_filename = archive_download_filename(handle)
    before = journal_positions()
    try:
        with ree_command_span("ree-archive", ree_id):
            received = command_dispatcher.build_archive(handle)
    except (HTTPException, WorkbenchUnavailableError):
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if received.size == 0:
        received.path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail="workbench returned an empty archive")
    record_archive(ree_id, received.sha256, received.size, before)
    spool = received.path.open("rb")
    received.path.unlink()
    size = received.size
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
