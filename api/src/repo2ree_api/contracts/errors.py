"""The error envelope every operation shares.

Strict: the envelope is the control-plane contract, so an unknown field on it is
a bug rather than a passthrough. ``ERROR_RESPONSES`` is the response table each
route spreads into its ``responses=``, so the documented failure modes cannot
drift route by route.
"""

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
    422: {"model": ErrorEnvelope, "description": "Request validation failed"},
    502: {"model": ErrorEnvelope, "description": "Workbench returned an invalid upstream response"},
    500: {"model": ErrorEnvelope, "description": "Internal server error"},
    503: {"model": ErrorEnvelope, "description": "Workbench or runtime agent unavailable"},
    507: {"model": ErrorEnvelope, "description": "Upload staging capacity exhausted"},
}
