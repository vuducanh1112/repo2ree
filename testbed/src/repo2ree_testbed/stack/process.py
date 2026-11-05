"""Running commands, waiting on what they start, and stopping it."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from repo2ree_testbed.artifacts import ROOT

ATTEMPTS = 30
_JSON = TypeAdapter[JsonValue](JsonValue)


def run(
    args: Sequence[str],
    *,
    cwd: Path = ROOT,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    silent = subprocess.DEVNULL if quiet and not capture else None
    return subprocess.run(
        list(args),
        cwd=cwd,
        env={**os.environ, **(env or {})},
        check=check,
        text=True,
        capture_output=capture,
        stdout=silent,
        stderr=silent,
    )


def capture(args: Sequence[str], *, cwd: Path = ROOT, env: Mapping[str, str] | None = None, check: bool = False) -> str:
    return run(args, cwd=cwd, env=env, check=check, capture=True).stdout.strip()


def lines(args: Sequence[str]) -> list[str]:
    return [line for line in capture(args).splitlines() if line]


def wait_until(description: str, probe: Callable[[], bool]) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        if probe():
            return
        print(f"  waiting for {description}... ({attempt}/{ATTEMPTS})")
        time.sleep(1)
    raise RuntimeError(f"{description} did not become ready")


def descendants(pid: int) -> list[int]:
    """Every process started under ``pid``, whatever session or group it moved to."""
    children: dict[int, list[int]] = {}
    for line in capture(["ps", "-A", "-o", "pid=,ppid="]).splitlines():
        child, parent = line.split()
        children.setdefault(int(parent), []).append(int(child))
    found: list[int] = []
    pending = [pid]
    while pending:
        for descendant in children.get(pending.pop(), []):
            found.append(descendant)
            pending.append(descendant)
    return found


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill a process and everything it started at once, as a crash of the machine or container it runs in would."""
    started = descendants(process.pid)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGSTOP)
    for pid in started:
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def fetch_as[T](url: str, shape: TypeAdapter[T], timeout: float = 1) -> T | None:
    """The document at ``url`` read as ``shape``; None when it cannot be fetched or has another shape."""
    document = fetch_json(url, timeout)
    try:
        return shape.validate_python(document) if document is not None else None
    except ValidationError:
        return None


def fetch_json(url: str, timeout: float = 1) -> JsonValue:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - a stack this process owns
            return _JSON.validate_python(json.load(response))
    except (OSError, ValueError, urllib.error.URLError, ValidationError):
        return None


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310 - a stack this process owns
            return int(response.status) < 400
    except (OSError, urllib.error.URLError):
        return False


def listed(url: str, key: str) -> int:
    document = fetch_json(url)
    items = document.get(key) if isinstance(document, dict) else None
    return len(items) if isinstance(items, list) else 0
