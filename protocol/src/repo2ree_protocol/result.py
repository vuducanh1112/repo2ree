from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # "succeeded" | "failed" | "canceled"
    exit_code: int = 0
    outputs: dict[str, Any] = {}
