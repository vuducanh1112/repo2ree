"""How long recipes took, as the dev shell's `just` recorded them (logs/just/, scripts/just_timing.py).

Each file is one invocation: a ``start`` line, a line per completed recipe, and an ``end`` line
unless it was interrupted. Lines this build cannot read are skipped, and a file without a start is
not an invocation. A recipe's lines do not name its arguments, so its timings are per recipe, not
per call.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import Field, TypeAdapter, ValidationError

from repo2ree_repoview.documents import Document, Record
from repo2ree_repoview.repository import ROOT

LOGS = ROOT / "logs" / "just"
SCHEMA = "repo2ree-just-timing/1"


class Start(Document):
    kind: Literal["start"]
    # `schema` itself would shadow pydantic's own attribute.
    version: str = Field("", alias="schema")
    invocation: str
    argv: tuple[str, ...]
    revision: str | None = None
    machine: str = "local"
    started: str


class Completed(Document):
    kind: Literal["recipe"]
    recipe: str
    seconds: float


class End(Document):
    kind: Literal["end"]
    exit: int
    seconds: float


LINE: TypeAdapter[Start | Completed | End] = TypeAdapter(Start | Completed | End)


@dataclass(frozen=True)
class Invocation:
    start: Start
    recipes: tuple[Completed, ...]
    end: End | None

    @property
    def command(self) -> str:
        return " ".join(self.start.argv) or "(default recipe)"


def read_invocation(path: Path) -> Invocation | None:
    start: Start | None = None
    recipes: list[Completed] = []
    end: End | None = None
    for text in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            line = LINE.validate_python(json.loads(text))
        except (ValueError, ValidationError):
            continue
        match line:
            case Start() if start is None and line.version == SCHEMA:
                start = line
            case Completed():
                recipes.append(line)
            case End():
                end = line
    return Invocation(start, tuple(recipes), end) if start is not None else None


def read_invocations(logs: Path = LOGS) -> list[Invocation]:
    """Every recorded invocation, oldest first."""
    found = [invocation for path in sorted(logs.glob("*/*.jsonl")) if (invocation := read_invocation(path))]
    return sorted(found, key=lambda invocation: invocation.start.started)


class Timing(Record):
    runs: int
    median: float
    last: float
    last_revision: str | None = None
    last_exit: int | None = None


class Timings(Record):
    """The overview's input: what the invocations it read amount to."""

    invocations: int
    # recipe -> machine -> how long it took
    recipes: dict[str, dict[str, Timing]]
    # top-level command -> machine -> its wall time, for the invocations that ended
    commands: dict[str, dict[str, Timing]]


def summarize(invocations: list[Invocation]) -> Timings:
    recipes: dict[str, dict[str, list[tuple[float, Invocation]]]] = defaultdict(lambda: defaultdict(list))
    commands: dict[str, dict[str, list[tuple[float, Invocation]]]] = defaultdict(lambda: defaultdict(list))
    for invocation in invocations:
        machine = invocation.start.machine
        for completed in invocation.recipes:
            recipes[completed.recipe][machine].append((completed.seconds, invocation))
        if invocation.end is not None:
            commands[invocation.command][machine].append((invocation.end.seconds, invocation))

    def timing(samples: list[tuple[float, Invocation]]) -> Timing:
        seconds, last = samples[-1]
        return Timing(
            runs=len(samples),
            median=round(median(value for value, _ in samples), 3),
            last=seconds,
            last_revision=last.start.revision,
            last_exit=last.end.exit if last.end is not None else None,
        )

    def per_machine(table: dict[str, dict[str, list[tuple[float, Invocation]]]]) -> dict[str, dict[str, Timing]]:
        return {
            name: {machine: timing(samples) for machine, samples in sorted(machines.items())}
            for name, machines in sorted(table.items())
        }

    return Timings(invocations=len(invocations), recipes=per_machine(recipes), commands=per_machine(commands))
