"""A CLI test's session: every ``ree`` command it ran, as it typed it, and what each answered.

The CLI showcase client appends one line per command to ``<test>/artifacts/cli-session.ndjson``; ``visualize``
lays the session beside the REE's history, so each command is shown with the REE as it left it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import JsonValue, ValidationError

from repo2ree_testbed.records import Record

SESSION = "cli-session.ndjson"
# The test's own directory, as the stack names it to the client.
TEST_DIR_VARIABLE = "E2E_TEST_DIR"
# A result kept whole up to this many bytes; a larger one (``show`` answers with every file) keeps its status alone.
RESULT_BYTES = 64 * 1024
STDIN_CHARACTERS = 8 * 1024
LOG_LINES = 200


class CliCommand(Record):
    """One ``ree`` command: the REE it ran against, its words, what it read and answered, and how long it took."""

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
    started: float
    finished: float

    @property
    def duration(self) -> float:
        return self.finished - self.started

    @property
    def status(self) -> str:
        """How the command ended, as its result says, or by its exit status where it printed none."""
        found = (self.result or {}).get("status")
        return str(found) if isinstance(found, str) else ("succeeded" if self.exit == 0 else f"exit {self.exit}")


def session_file() -> Path | None:
    """Where this test's session goes; None outside a stack that names the test's directory."""
    directory = os.environ.get(TEST_DIR_VARIABLE)
    return Path(directory) / "artifacts" / SESSION if directory else None


def kept_result(line: str) -> tuple[dict[str, JsonValue] | None, int]:
    """The result a command printed, whole while small; for a large one, how it ended and why, without outputs."""
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
    """The commands a session holds, in the order they ran; a line that is no command is passed over."""
    if not path.is_file():
        return ()
    commands = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            commands.append(CliCommand.model_validate_json(line))
        except ValidationError:
            continue
    return tuple(commands)
