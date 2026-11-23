from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] | list[dict[str, Any]] | None = None
    retryable: bool = False


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope, "description": "Invalid request or operation precondition"},
    404: {"model": ErrorEnvelope, "description": "REE, run, file, or artifact not found"},
    409: {"model": ErrorEnvelope, "description": "Version or idempotency conflict"},
    413: {"model": ErrorEnvelope, "description": "Upload exceeds the configured size limit"},
    415: {"model": ErrorEnvelope, "description": "Request body is not application/json"},
    422: {"model": ErrorEnvelope, "description": "Request validation failed"},
    502: {"model": ErrorEnvelope, "description": "Workbench returned an invalid upstream response"},
    500: {"model": ErrorEnvelope, "description": "Internal server error"},
    503: {"model": ErrorEnvelope, "description": "Compute provider or workbench unavailable"},
    507: {"model": ErrorEnvelope, "description": "Upload staging capacity exhausted"},
}
