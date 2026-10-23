"""Serve behaviour journals as their owners wrote them, for collection over the control plane.

Records are returned byte for byte: the reader that judges them (the
assurance checker) must see what the owner wrote, gaps and all. Only complete
lines are served, so a read racing an append never returns a torn record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

JOURNAL_ID = re.compile(r"^(?P<process>[a-z][a-z0-9-]*)-(?P<epoch>[0-9]{6})$")


@dataclass(frozen=True)
class JournalFile:
    id: str
    process: str
    epoch: int
    path: Path


def journal_files(directory: Path) -> list[JournalFile]:
    paths = sorted(directory.glob("*.ndjson")) if directory.is_dir() else []
    return [
        JournalFile(path.stem, match["process"], int(match["epoch"]), path)
        for path in paths
        if (match := JOURNAL_ID.match(path.stem))
    ]


def journal_file(directory: Path, journal_id: str) -> JournalFile | None:
    if not JOURNAL_ID.match(journal_id):
        return None
    return next((file for file in journal_files(directory) if file.id == journal_id), None)


def complete_lines(path: Path) -> list[bytes]:
    """Every record line the owner finished writing, in order."""
    data = path.read_bytes()
    return data[: data.rfind(b"\n") + 1].splitlines(keepends=True)


def records_after(path: Path, after: int) -> bytes:
    """The complete records whose sequence number is above ``after``, as written.

    A line without a readable sequence number is kept: deciding what it means is
    the checker's job, not the server's.
    """
    kept: list[bytes] = []
    for line in complete_lines(path):
        seq = _sequence(line)
        if seq is None or seq > after:
            kept.append(line)
    return b"".join(kept)


def last_position(path: Path) -> int:
    """The highest sequence number among the complete records: one side of a cut."""
    return max((seq for line in complete_lines(path) if (seq := _sequence(line)) is not None), default=0)


def positions(directory: Path) -> dict[str, int]:
    return {file.id: last_position(file.path) for file in journal_files(directory)}


def _sequence(line: bytes) -> int | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    seq = record.get("seq") if isinstance(record, dict) else None
    return seq if isinstance(seq, int) else None
