from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import JsonValue, ValidationError

from repo2ree_testbed.records import Record

SESSION = "cli-session.ndjson"
TEST_DIR_VARIABLE = "E2E_TEST_DIR"
RESULT_BYTES = 64 * 1024
STDIN_CHARACTERS = 8 * 1024
LOG_LINES = 200


class CliCommand(Record):
    ree: str
    words: tuple[str, ...]
    run_id: str | None = None
    stdin: str | None = None
    stdin_bytes: int = 0
    exit: int
    result: dict[str, JsonValue] | None = None
    result_bytes: int = 0
    stdout_bytes: int = 0
    log: tuple[str, ...] = ()
    started: float | None = None
    finished: float | None = None

    @property
    def duration(self) -> float | None:
        return None if self.started is None or self.finished is None else self.finished - self.started

    @property
    def status(self) -> str:
        found = (self.result or {}).get("status")
        return str(found) if isinstance(found, str) else ("succeeded" if self.exit == 0 else f"exit {self.exit}")


def session_file() -> Path | None:
    directory = os.environ.get(TEST_DIR_VARIABLE)
    return Path(directory) / "artifacts" / SESSION if directory else None


def kept_result(line: str) -> tuple[dict[str, JsonValue] | None, int]:
    try:
        parsed: Any = json.loads(line)
    except ValueError:
        return None, len(line)
    if not isinstance(parsed, dict):
        return None, len(line)
    if len(line) <= RESULT_BYTES:
        return parsed, len(line)
    return {key: parsed[key] for key in ("status", "exit_code", "failure") if key in parsed}, len(line)


def kept_stdin(stdin: bytes | None) -> tuple[str | None, int]:
    if not stdin:
        return None, 0
    text = stdin.decode(errors="replace")
    return (text if len(text) <= STDIN_CHARACTERS else text[:STDIN_CHARACTERS] + "\n…"), len(stdin)


def append(path: Path, command: CliCommand) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as session:
        session.write(command.model_dump_json(exclude_none=True) + "\n")


def read_session(path: Path) -> tuple[CliCommand, ...]:
    if not path.is_file():
        return ()
    commands = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            commands.append(CliCommand.model_validate_json(line))
        except ValidationError:
            continue
    return tuple(commands)
