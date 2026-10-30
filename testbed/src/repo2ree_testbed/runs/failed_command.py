"""The last workbench command that failed in a run, read off its dossier's spans: an execution fact."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# A line that reports a failure, whatever tool printed it (pip, BuildKit, apt, a shell).
_FAILURE = re.compile(r"error|fail|denied|not found|no such|timed? ?out", re.IGNORECASE)
_LINE_LIMIT = 240


class _Status(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status_code: str = ""


class _Span(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    end_time: str = ""
    status: _Status = Field(default_factory=_Status)
    attributes: dict[str, object] = Field(default_factory=dict)


@dataclass(frozen=True)
class FailedCommand:
    argv: str
    exit_code: object
    stderr_tail: str

    def failure_lines(self) -> list[str]:
        """The first and the last failure line of the tail: commonly what went wrong first, then how it ended."""
        found = [line.strip() for line in self.stderr_tail.splitlines() if _FAILURE.search(line)]
        picked = found[:1] + found[-1:] if len(found) > 1 else found
        return [_shortened(line) for line in picked]

    def summary(self) -> str:
        head = f"`{self.argv}` exited {self.exit_code}"
        lines = self.failure_lines()
        return f"{head}: {' … '.join(lines)}" if lines else head


def _shortened(line: str) -> str:
    return line if len(line) <= _LINE_LIMIT else line[: _LINE_LIMIT - 1] + "…"


def last_failed_command(telemetry: Path) -> FailedCommand | None:
    """The latest-ending ``process.exec`` span that failed and was not canceled, if the run recorded one."""
    latest: _Span | None = None
    for path in sorted(telemetry.glob("*.ndjson")) if telemetry.is_dir() else []:
        for line in path.read_text(errors="replace").splitlines():
            if '"process.exec"' not in line:
                continue
            try:
                span = _Span.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValidationError):
                continue
            failed = span.status.status_code == "ERROR" and span.attributes.get("repo2ree.canceled") is not True
            if span.name == "process.exec" and failed and (latest is None or span.end_time > latest.end_time):
                latest = span
    if latest is None:
        return None
    attributes = latest.attributes
    return FailedCommand(
        argv=str(attributes.get("repo2ree.exec.argv", "?")),
        exit_code=attributes.get("repo2ree.exit_code", "?"),
        stderr_tail=str(attributes.get("repo2ree.exec.stderr_tail", "")),
    )
