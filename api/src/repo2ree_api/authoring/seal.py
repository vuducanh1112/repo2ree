"""The seal step, and the bundle that carries a sealed REE somewhere else.

Sealing freezes the record; the archive is how it travels, and ``ree:load`` is
the other end of that journey — the upload sequence that makes a fresh REE *be*
a bundle someone else downloaded. Load is grouped with seal rather than with
source acquisition because it restores a whole REE (intent, source, evidence),
not an upstream snapshot.
"""

from __future__ import annotations

import tempfile
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from repo2ree_api.authoring.upload_runs import StagedUploadLog, start_staged_upload_run
from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    ReeBundleLoadPayload,
    ReeDocument,
    ReeSealPayload,
    RunSummary,
    UploadInitPayload,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.control.run_orchestration import run_summary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.archives import archive_download_filename, spool_chunks
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_api.workbench.uploads import mint_upload_token, stage_upload_bytes
from repo2ree_protocol import LoadReeBundleCommand, SealReeCommand
from repo2ree_protocol.command import LoadReeBundleArgs, SealReeArgs

seal_router = APIRouter(tags=["rees"])


@seal_router.post(
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
    run_state = start_staged_upload_run(
        ree_id,
        upload_token=payload.upload_token,
        archive_name=payload.archive_name,
        purpose="bundle",
        operation="ree-load",
        run_id_prefix="ree-load",
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


@seal_router.get(
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
