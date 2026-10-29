from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import pytest

from repo2ree_testbed.run_watch import RunNotSettledError, RunWatch, settle_run

FAST = RunWatch(stall=0.3, budget=2.0, poll=0.02)


class FakeRun:
    """A run whose status and log follow a script of (seconds since start, status, new log lines)."""

    def __init__(self, script: list[tuple[float, str, list[str]]]):
        self.script = script
        self.started = time.monotonic()
        self.log: list[str] = []

    def get(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        elapsed = time.monotonic() - self.started
        status = "queued"
        lines: list[str] = []
        for at, step_status, step_lines in self.script:
            if elapsed >= at:
                status = step_status
                lines.extend(step_lines)
        self.log = lines
        if path.endswith("/logs"):
            after = int(params.get("cursor", "0"))
            entries = [
                {"seq": seq, "level": "info", "message": message}
                for seq, message in enumerate(self.log, start=1)
                if seq > after
            ]
            return {"entries": entries, "next_cursor": str(entries[-1]["seq"]) if entries else None}
        return {"run_id": "run-1", "operation": "build", "status": status}


def test_a_run_that_settles_is_returned_with_its_log_tail() -> None:
    run = FakeRun([(0, "running", ["pulling"]), (0.1, "succeeded", ["done"])])
    settled = settle_run(run.get, "ree-1", "run-1", FAST)
    assert settled.run["status"] == "succeeded"
    assert settled.tail == ("[info] pulling", "[info] done")


def test_a_failed_run_is_returned_not_raised() -> None:
    run = FakeRun([(0, "running", []), (0.1, "failed", ["exit 3"])])
    assert settle_run(run.get, "ree-1", "run-1", FAST).run["status"] == "failed"


def test_a_run_that_keeps_logging_outlasts_its_stall_window() -> None:
    script: list[tuple[float, str, list[str]]] = [(0.2 * i, "running", [f"line {i}"]) for i in range(6)]
    run = FakeRun([*script, (1.2, "succeeded", [])])
    settled = settle_run(run.get, "ree-1", "run-1", FAST)
    assert settled.run["status"] == "succeeded"
    assert settled.seconds > FAST.stall


def test_a_run_that_goes_quiet_fails_with_what_it_said_last() -> None:
    run = FakeRun([(0, "running", ["pulling python:3.11-slim"])])
    with pytest.raises(RunNotSettledError, match=r"logged nothing for 0s while running(?s:.*)pulling python"):
        settle_run(run.get, "ree-1", "run-1", FAST)


def test_a_run_past_its_budget_fails_even_while_logging() -> None:
    run = FakeRun([(0.1 * i, "running", [f"line {i}"]) for i in range(40)])
    with pytest.raises(RunNotSettledError, match="still running after 1s"):
        settle_run(run.get, "ree-1", "run-1", RunWatch(stall=0.5, budget=1.0, poll=0.02))


def test_a_silent_watch_waits_out_the_whole_budget() -> None:
    run = FakeRun([(0, "running", []), (0.6, "failed", [])])
    assert settle_run(run.get, "ree-1", "run-1", RunWatch.silent(2.0)).run["status"] == "failed"
