from fastapi import APIRouter, HTTPException, Request

from repo2ree.service.storage.review_files import (
    ReviewUploadCompletePayload,
    ReviewUploadInitPayload,
    complete_review_upload,
    get_review,
    init_review_upload,
    store_review_upload_bytes,
)


review_ree_router = APIRouter()


@review_ree_router.post("/api/v1/reviews:upload-init")
def review_upload_init_route(payload: ReviewUploadInitPayload):
    try:
        return init_review_upload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@review_ree_router.put("/api/v1/reviews/{review_id}/upload/{upload_token}")
async def review_upload_put_route(review_id: str, upload_token: str, request: Request):
    try:
        data = await request.body()
        return store_review_upload_bytes(review_id, upload_token, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@review_ree_router.post("/api/v1/reviews/{review_id}:upload-complete")
def review_upload_complete_route(review_id: str, payload: ReviewUploadCompletePayload):
    try:
        return complete_review_upload(review_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@review_ree_router.get("/api/v1/reviews/{review_id}")
def get_review_route(review_id: str):
    try:
        return get_review(review_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
