"""Wait for a run to settle, failing when it goes quiet rather than when it is slow.

The Python twin of gui/tests/runs.ts: the same rules, for the API-driven tiers.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

TERMINAL = frozenset({"succeeded", "failed", "canceled"})

type Getter = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


@dataclass(frozen=True)
class RunWatch:
    """How long a run may log nothing before it counts as stalled, and the overall backstop."""

    stall: float
    budget: float
    poll: float = 0.2

    @classmethod
    def silent(cls, budget: float) -> RunWatch:
        """For a run expected to go quiet, a frozen or lost workbench above all: only the budget applies."""
        return cls(stall=budget, budget=budget)


INSTANT_RUN = RunWatch(stall=30, budget=180)
NETWORK_RUN = RunWatch(stall=120, budget=1200)


class RunNotSettledError(AssertionError):
    pass


@dataclass(frozen=True)
class SettledRun:
    run: dict[str, Any]
    seconds: float
    longest_silence: float
    tail: tuple[str, ...]


class _Client(Protocol):
    def get(self, url: str, *, params: Mapping[str, str] | None = ...) -> Any: ...


def client_getter(client: _Client) -> Getter:
    """A getter over an ``httpx.Client`` or FastAPI ``TestClient``, failing on any non-200."""

    def get(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        response = client.get(path, params=params or None)
        if response.status_code != 200:
            raise RunNotSettledError(f"GET {path}: {response.status_code} {response.text}")
        return dict(response.json())

    return get


def settle_run(get: Getter, ree_id: str, run_id: str, watch: RunWatch = INSTANT_RUN) -> SettledRun:
    """Poll the run until it settles, whatever its outcome.

    Raises :class:`RunNotSettledError`, with the run's last log lines, when it logs
    nothing for ``watch.stall`` seconds or is still going after ``watch.budget``.
    """
    base = f"/api/v1/rees/{ree_id}/runs/{run_id}"
    started = last_progress = time.monotonic()
    longest_silence = 0.0
    status = ""
    cursor: str | None = None
    tail: deque[str] = deque(maxlen=20)

    def failure(reason: str) -> RunNotSettledError:
        lines = "\n".join(tail) or "(none)"
        return RunNotSettledError(f"run {run_id} {reason}; last log lines:\n{lines}")

    while True:
        now = time.monotonic()
        run = dict(get(base, {}))
        logs = get(f"{base}/logs", {} if cursor is None else {"cursor": cursor})
        entries = list(logs.get("entries", []))
        if entries or run["status"] != status:
            longest_silence = max(longest_silence, now - last_progress)
            last_progress = now
        tail.extend(f"[{entry.get('level')}] {entry.get('message')}" for entry in entries)
        cursor = logs.get("next_cursor") or cursor
        status = str(run["status"])

        if status in TERMINAL:
            return SettledRun(run=run, seconds=now - started, longest_silence=longest_silence, tail=tuple(tail))
        if now - last_progress > watch.stall:
            raise failure(f"{run.get('operation')} logged nothing for {watch.stall:.0f}s while {status}")
        if now - started > watch.budget:
            raise failure(f"{run.get('operation')} still {status} after {watch.budget:.0f}s")
        time.sleep(watch.poll)
