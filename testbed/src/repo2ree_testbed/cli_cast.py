"""A CLI test's session as a terminal recording: each ``ree`` command at a prompt, then what it printed, when.

The CLI showcase client appends every command to ``<test>/artifacts/cli-session.cast`` (asciicast v2) beside the
session; ``asciinema play`` plays it back with idle time cut to ``IDLE_SECONDS``. Each prompt names the directory the
command ran in. The bytes are those the command printed, stdout and stderr as they arrived; ``ree`` prints the same
with or without a terminal.
"""

from __future__ import annotations

import codecs
import json
import os
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.cli_session import TEST_DIR_VARIABLE

CAST = "cli-session.cast"
WIDTH = 160
HEIGHT = 48
IDLE_SECONDS = 2.0

type Stream = Literal["stdout", "stderr"]


class Printed(NamedTuple):
    """A chunk a command printed, on which stream, and when it arrived."""

    at: float
    stream: Stream
    data: bytes


class Header(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: Literal[2] = 2
    width: int = WIDTH
    height: int = HEIGHT
    timestamp: int
    idle_time_limit: float = IDLE_SECONDS
    title: str


def cast_file() -> Path | None:
    """Where this test's recording goes; None outside a stack that names the test's directory."""
    directory = os.environ.get(TEST_DIR_VARIABLE)
    return Path(directory) / "artifacts" / CAST if directory else None


def prompt(command: Sequence[str], stdin_bytes: int, where: str | None = None) -> str:
    """The command as typed in ``where``, with what it read on stdin noted beside it."""
    typed = shlex.join(command)
    if stdin_bytes:
        typed += f"  # {stdin_bytes} bytes on stdin"
    directory = f"\x1b[36m{where}\x1b[0m " if where else ""
    return f"{directory}\x1b[1m$ {typed}\x1b[0m\r\n"


def _terminal(text: str) -> str:
    """Text as a terminal is sent it: every line ends in CR LF."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _binary(printed: Sequence[Printed]) -> frozenset[Stream]:
    """The streams that carried bytes no terminal shows as text, such as an archive written to stdout."""
    streams: set[Stream] = set()
    for stream in ("stdout", "stderr"):
        try:
            b"".join(chunk.data for chunk in printed if chunk.stream == stream).decode()
        except UnicodeDecodeError:
            streams.add(stream)
    return frozenset(streams)


def _origin(path: Path, started: float) -> int:
    """The recording's start, from its header; a recording not yet begun begins now."""
    if path.is_file():
        with path.open(encoding="utf-8") as cast:
            return Header.model_validate_json(cast.readline()).timestamp
    header = Header(timestamp=int(started), title=path.parent.parent.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header.model_dump_json() + "\n", encoding="utf-8")
    return header.timestamp


def append_command(
    path: Path,
    command: Sequence[str],
    *,
    where: str | None = None,
    stdin_bytes: int,
    started: float,
    finished: float,
    printed: Sequence[Printed],
) -> None:
    """Add one command to the recording: its prompt when it started, each chunk when it arrived.

    A stream that is not text is recorded as a note of how many bytes it carried, when its last chunk arrived.
    """
    origin = _origin(path, started)
    binary = _binary(printed)
    decoders = {stream: codecs.getincrementaldecoder("utf-8")(errors="replace") for stream in ("stdout", "stderr")}
    shown = [chunk for chunk in printed if chunk.stream not in binary]
    arrived = [(chunk.at, decoders[chunk.stream].decode(chunk.data)) for chunk in shown]
    for stream in sorted(binary):
        chunks = [chunk for chunk in printed if chunk.stream == stream]
        size = sum(len(chunk.data) for chunk in chunks)
        arrived.append((chunks[-1].at, f"\x1b[2m[{size} bytes on {stream}, not text]\x1b[0m\n"))
    arrived.sort(key=lambda event: event[0])
    remainder = [(finished, decoder.decode(b"", final=True)) for decoder in decoders.values()]
    events = [(started, prompt(command, stdin_bytes, where))]
    events += [(at, _terminal(text)) for at, text in (*arrived, *remainder) if text]
    if len(events) > 1 and not events[-1][1].endswith("\n"):
        events.append((finished, "\r\n"))
    elapsed = 0.0
    with path.open("a", encoding="utf-8") as cast:
        for at, text in events:
            elapsed = max(elapsed, round(at - origin, 6))
            cast.write(json.dumps([elapsed, "o", text]) + "\n")
