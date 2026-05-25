"""Thin API adapter for review upload and lifecycle operations.

All business logic and filesystem I/O lives in
``repo2ree_core.storage.review_ops``. This module re-exports every
symbol that the rest of the API package imports, binding the storage root
to ``service_settings.REVIEWS_STORAGE_DIR``.

Payload models stay here because they are FastAPI request/response shapes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

import repo2ree_core.storage.review_ops as _ops
from repo2ree_api.settings import service_settings


# ================================================
# Request / response payload models
# ================================================


class ReviewUploadInitPayload(BaseModel):
    fileName: str
    size: int
    contentType: str


class ReviewUploadCompletePayload(BaseModel):
    uploadToken: str
    archiveName: str


# ================================================
# Storage root accessor
# ================================================


def review_root() -> Path:
    return service_settings.REVIEWS_STORAGE_DIR


def ensure_review_root() -> None:
    review_root().mkdir(parents=True, exist_ok=True)


# ================================================
# Path accessors
# ================================================


def review_dir(review_id: str) -> Path:
    return _ops.review_dir(review_root(), review_id)


def review_workspace_dir(review_id: str) -> Path:
    return _ops.review_workspace_dir(review_root(), review_id)


def review_metadata_path(review_id: str) -> Path:
    return _ops.review_metadata_path(review_root(), review_id)


# ================================================
# Operations
# ================================================


def get_review(review_id: str) -> dict[str, Any]:
    return _ops.get_review(review_root(), review_id)


def init_review_upload(payload: ReviewUploadInitPayload) -> dict[str, Any]:
    result = _ops.init_review_upload(
        review_root(),
        file_name=payload.fileName,
        size=payload.size,
        content_type=payload.contentType,
    )
    review_id = result["reviewId"]
    token = result["uploadToken"]
    result["uploadUrl"] = f"/api/v1/reviews/{review_id}/upload/{token}"
    return result


def store_review_upload_bytes(
    review_id: str, token: str, data: bytes
) -> dict[str, Any]:
    return _ops.store_review_upload_bytes(review_root(), review_id, token, data)


def complete_review_upload(
    review_id: str, payload: ReviewUploadCompletePayload
) -> dict[str, Any]:
    return _ops.complete_review_upload(
        review_root(), review_id, payload.uploadToken, payload.archiveName
    )
