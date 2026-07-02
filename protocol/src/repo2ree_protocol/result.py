from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# The terminal status of any executed action, shared by every layer that
# produces or relays one (executor handlers, agent, manager, run registry).
ActionStatus = Literal["succeeded", "failed", "canceled"]


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ActionStatus
    exit_code: int = 0
    outputs: dict[str, Any] = {}
