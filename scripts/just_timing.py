#!/usr/bin/env python3
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
MARKER = "REPO2REE_JUST_TIMING"
KEPT_DAYS = 30
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
    oldest = (today - timedelta(days=KEPT_DAYS)).date().isoformat()
    for day in logs.glob("????-??-??"):
        if day.name < oldest:
            shutil.rmtree(day, ignore_errors=True)


class Chunked(Protocol):
    def read1(self, size: int = ..., /) -> bytes: ...


def forward(source: Chunked, target: IO[bytes], recorder: Recorder) -> None:
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
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda signum, _frame: child.send_signal(signum))
    if child.stderr is None:
        raise RuntimeError("just's stderr was not piped")
    source = cast("Chunked", child.stderr)
    reader = threading.Thread(target=forward, args=(source, sys.stderr.buffer, recorder), daemon=True)
    reader.start()
    code = child.wait()
    reader.join(timeout=2)
    exit_code = code if code >= 0 else 128 - code
    recorder.write({"kind": "end", "exit": exit_code, "seconds": round(time.monotonic() - begun, 3)})
    recorder.close()
    return exit_code


def run_plainly(real: str, args: list[str]) -> NoReturn:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.execv(real, [real, *args])  # noqa: S606


def main(argv: list[str]) -> int:
    real, args = argv[1], argv[2:]
    if os.environ.get(MARKER) or not runs_recipes(args):
        run_plainly(real, args)
    return record(real, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
