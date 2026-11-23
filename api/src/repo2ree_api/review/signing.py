from __future__ import annotations

from fastapi import APIRouter, Request

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    RunSummary,
    SignReviewPayload,
    UploadInitPayload,
    UploadInitResponse,
    UploadStoredResponse,
)
from repo2ree_api.contracts.runs import runs
from repo2ree_api.control.run_orchestration import run_summary
from repo2ree_api.control.upload_runs import StagedUploadLog, start_staged_upload_run
from repo2ree_api.workbench.uploads import mint_upload_token, stage_upload_bytes
from repo2ree_protocol.command import SignReviewArgs, SignReviewCommand

review_signing_router = APIRouter(tags=["reviews"])


@review_signing_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/signature:upload-init",
    operation_id="initializeReviewSignatureUpload",
    response_model=UploadInitResponse,
    responses=ERROR_RESPONSES,
)
def review_signature_upload_init_route(ree_id: str, review_id: str, payload: UploadInitPayload) -> UploadInitResponse:
    return UploadInitResponse.model_validate(
        mint_upload_token(
            ree_id,
            payload,
            upload_route=f"reviews/{review_id}/signature:upload",
            purpose="signature",
            action="sign_review",
        )
    )


@review_signing_router.put(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/signature:upload/{upload_token}",
    operation_id="uploadReviewSignatureBytes",
    response_model=UploadStoredResponse,
    responses=ERROR_RESPONSES,
)
async def store_review_signature_bytes_route(
    ree_id: str, review_id: str, upload_token: str, request: Request
) -> UploadStoredResponse:
    del review_id
    return UploadStoredResponse.model_validate(
        await stage_upload_bytes(ree_id, upload_token, request, purpose="signature")
    )


@review_signing_router.post(
    "/api/v1/rees/{ree_id}/sign-review/{review_id}",
    operation_id="signReview",
    openapi_extra=runs("sign_review"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def sign_review_route(ree_id: str, review_id: str, payload: SignReviewPayload) -> RunSummary:
    run_state = start_staged_upload_run(
        ree_id,
        upload_token=payload.upload_token,
        archive_name=payload.archive_name,
        purpose="signature",
        action="sign_review",
        command=SignReviewCommand(
            args=SignReviewArgs(
                review_id=review_id, upload_token=payload.upload_token, archive_name=payload.archive_name
            )
        ),
        request_payload={
            "review_id": review_id,
            "upload_token": payload.upload_token,
            "archive_name": payload.archive_name,
        },
        messages=StagedUploadLog(
            starting=f"Signing review {review_id} with {payload.archive_name}",
            canceled="Review signing canceled",
            copied="Signature copied; adding it to the review",
            succeeded="Review signed",
        ),
        idempotency_key=payload.idempotency_key,
    )
    return RunSummary.model_validate(run_summary(run_state))
