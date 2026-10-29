#!/usr/bin/env python3
"""Run `just` and record how long each of its recipes took, in logs/just/.

The dev shell's `just` is this script in front of the real one: ``just_timing.py REAL_JUST ARGS...``.
Only the outermost `just` of an invocation records. It runs the real one with ``JUST_TIME=true``,
passes its stderr through as it arrives, and writes one JSON line per recipe that just reports
(``---> RECIPE completed in Ns``) to ``logs/just/<date>/<time>-<id>.jsonl``, between a ``start``
and an ``end`` line. A `just` that one of its recipes starts finds ``REPO2REE_JUST_TIMING`` set
and hands over to the real one at once: its lines reach the outermost one through the stderr they
share, so every recipe is recorded once. Commands that run no recipe (--list, --dump, ...) are
not recorded.

Recording never changes what just does: the exit code is just's own, and a record that cannot be
written is warned about once and given up.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Any, NoReturn, Protocol, cast
from uuid import uuid4

SCHEMA = "repo2ree-just-timing/1"
ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs" / "just"
# Set for every process of an invocation that records: the file it records into.
MARKER = "REPO2REE_JUST_TIMING"
# A day directory older than this is removed when an invocation starts.
KEPT_DAYS = 30
# Options under which just runs no recipe.
NOT_RUNS = frozenset(
    {
        "--changelog",
        "--check",
        "--choose",
        "--completions",
        "--dry-run",
        "--dump",
        "--edit",
        "--evaluate",
        "--fmt",
        "--groups",
        "--help",
        "--init",
        "--list",
        "--man",
        "--request",
        "--show",
        "--summary",
        "--usage",
        "--variables",
        "--version",
        "-V",
        "-e",
        "-h",
        "-l",
        "-n",
        "-s",
    }
)
COMPLETED = re.compile(r"^---> (\S+) completed in ([0-9.]+)s$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def runs_recipes(args: list[str]) -> bool:
    for arg in args:
        if arg == "--":
            return True
        if arg.split("=", 1)[0] in NOT_RUNS:
            return False
    return True


def completed(line: str) -> tuple[str, float] | None:
    """The recipe and seconds of a line `just --time` prints, if it is one."""
    match = COMPLETED.match(ANSI.sub("", line).rstrip("\r\n"))
    return (match[1], float(match[2])) if match else None


def git(*args: str) -> str | None:
    try:
        run = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return run.stdout.strip() if run.returncode == 0 else None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Recorder:
    """Lines appended to one invocation's file; the first failure to write ends the recording."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: IO[str] | None = None
        self.failed = False

    def write(self, record: dict[str, Any]) -> None:
        if self.failed:
            return
        try:
            if self.stream is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.stream = self.path.open("a", encoding="utf-8")
            self.stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            self.stream.flush()
        except OSError as error:
            sys.stderr.write(f">> just timings are not recorded ({error})\n")
            self.failed = True
            self.close()

    def close(self) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def prune(logs: Path, today: datetime) -> None:
    """Remove the day directories older than KEPT_DAYS; whatever cannot be removed stays."""
    oldest = (today - timedelta(days=KEPT_DAYS)).date().isoformat()
    for day in logs.glob("????-??-??"):
        if day.name < oldest:
            shutil.rmtree(day, ignore_errors=True)


class Chunked(Protocol):
    """A stream that returns what is there now, as just's piped stderr does."""

    def read1(self, size: int = ..., /) -> bytes: ...


def forward(source: Chunked, target: IO[bytes], recorder: Recorder) -> None:
    """Pass ``source`` to ``target`` as it arrives, recording every completed recipe it reports.

    It reads to the end even when ``target`` is gone (``just ... 2>&1 | head``), so just never
    blocks on a pipe nobody empties.
    """
    pending = b""
    shown: IO[bytes] | None = target
    while chunk := source.read1(65536):
        if shown is not None:
            try:
                shown.write(chunk)
                shown.flush()
            except OSError:
                shown = None
        pending += chunk
        *lines, pending = pending.split(b"\n")
        for line in lines:
            if found := completed(line.decode(errors="replace")):
                recorder.write({"kind": "recipe", "recipe": found[0], "seconds": found[1], "at": now()})


def record(real: str, args: list[str]) -> int:
    started = datetime.now(UTC)
    invocation = os.environ.setdefault("REPO2REE_TEST_RUN_ID", uuid4().hex)
    path = LOGS / started.date().isoformat() / f"{started:%H%M%S}-{uuid4().hex[:8]}.jsonl"
    prune(LOGS, started)
    recorder = Recorder(path)
    recorder.write(
        {
            "schema": SCHEMA,
            "kind": "start",
            "invocation": invocation,
            "argv": args,
            "cwd": os.path.relpath(Path.cwd(), ROOT),
            "revision": git("rev-parse", "HEAD"),
            "machine": os.environ.get("REPO2REE_MACHINE") or "local",
            "host": socket.gethostname(),
            "cpus": os.cpu_count(),
            "started": now(),
        }
    )
    colour = ["--color", "always"] if sys.stderr.isatty() and not any(a.startswith("--color") for a in args) else []
    env = {**os.environ, MARKER: str(path), "JUST_TIME": "true"}
    begun = time.monotonic()
    try:
        child = subprocess.Popen([real, *colour, *args], env=env, stderr=subprocess.PIPE)
    except OSError as error:
        sys.stderr.write(f">> just timings are not recorded ({error})\n")
        run_plainly(real, args)
    # Only now: a child would inherit the ignored SIGINT. Ctrl-C reaches just through the terminal,
    # and this process waits for it to end and records that; a SIGTERM is passed on.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda signum, _frame: child.send_signal(signum))
    if child.stderr is None:
        raise RuntimeError("just's stderr was not piped")
    source = cast("Chunked", child.stderr)
    reader = threading.Thread(target=forward, args=(source, sys.stderr.buffer, recorder), daemon=True)
    reader.start()
    code = child.wait()
    # Done when just is: a process a recipe left behind may hold stderr open for as long as it likes.
    reader.join(timeout=2)
    exit_code = code if code >= 0 else 128 - code
    recorder.write({"kind": "end", "exit": exit_code, "seconds": round(time.monotonic() - begun, 3)})
    recorder.close()
    return exit_code


def run_plainly(real: str, args: list[str]) -> NoReturn:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.execv(real, [real, *args])  # noqa: S606 — the real just takes this process's place, arguments as given


def main(argv: list[str]) -> int:
    real, args = argv[1], argv[2:]
    if os.environ.get(MARKER) or not runs_recipes(args):
        run_plainly(real, args)
    return record(real, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
