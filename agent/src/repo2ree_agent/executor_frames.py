"""Translate executor stdout/stderr into typed protocol frames and results."""

from __future__ import annotations

import json

from repo2ree_protocol.agent import AgentFrame, LogFrame, SpanFrame
from repo2ree_protocol.result import ActionResult


def executor_line_to_frame(line: str) -> AgentFrame | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return LogFrame(stream="system", level="info", message=line)
    if event.get("type") == "log":
        return LogFrame(stream=event["stream"], level=event["level"], message=event["message"])
    if event.get("type") == "span":
        return SpanFrame(payload=event["payload"])
    return LogFrame(stream="system", level="info", message=line)


def parse_action_result(stdout: str, returncode: int) -> ActionResult:
    if stdout:
        try:
            return ActionResult.model_validate_json(stdout)
        except ValueError:
            pass
    return ActionResult.failed(
        "internal",
        f"executor produced no valid result (exit {returncode})",
        origin="agent",
        exit_code=returncode or 1,
    )
