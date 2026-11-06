from __future__ import annotations

import asyncio
import json
import os
import signal
import stat
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame, LogFrame
from repo2ree_protocol.result import ActionResult
from repo2ree_workbench.executions import (
    _WRAPPER,
    Executions,
    Identity,
    ReeBusyError,
    UnknownExecutionError,
    _birth,
)
from repo2ree_workbench.executor_process import LocalExecutor
from repo2ree_workbench.journal import store_journal

INTERRUPTED = {
    "status": "failed",
    "exit_code": 1,
    "failure": {"category": "internal", "message": "interrupted", "origin": "core", "retryable": True},
    "history": {
        "selection_version": 2,
        "attempt_id": "x",
        "scope": ".",
        "capture_status": "captured",
        "operation_status": "interrupted",
        "after_snapshot_id": "c" * 40,
        "changed": False,
    },
}


def fake_executor(tmp_path: Path, execute: str = "") -> Path:
    """An executor whose ``execute`` logs a line, runs ``execute``, then reports success with its context."""
    path = tmp_path / "repo2ree-exec"
    marker = tmp_path / "marker"
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  execute) cat >/dev/null\n"
        '    echo \'{"type":"log","stream":"stdout","level":"info","message":"one"}\' >&2\n'
        "    echo two >&2\n"
        f"    {execute}\n"
        '    printf \'{"status":"succeeded","context":%s}\\n\' "$7" ;;\n'
        f'  cancel-run) touch "{marker}" ;;\n'
        f"  settle-attempt) printf '%s\\n' '{json.dumps(INTERRUPTED)}' ;;\n"
        "esac\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def executions(tmp_path: Path, execute: str = "", **options: float) -> Executions:
    store = tmp_path / "store"
    store.mkdir(exist_ok=True)
    return Executions(LocalExecutor(store, str(fake_executor(tmp_path, execute))), poll=0.02, **options)  # type: ignore[arg-type]


def start(runs: Executions, ree_id: str = "ree", run_id: str = "run-1", **context: str) -> ExecutionContext:
    started = ExecutionContext.new(ree_id=ree_id).model_copy(update=context)
    asyncio.run(runs.start(json.dumps({"operation": "lint_scripts"}), run_id, {}, started, ree_id=ree_id))
    return started


def follow(runs: Executions, attempt_id: str, ree_id: str = "ree", after: int = 0) -> tuple[list[Frame], ActionResult]:
    follower = runs.follow(ree_id, attempt_id, after)
    frames: list[Frame] = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        read, result = follower.read()
        frames += read
        if result is not None:
            return frames, result
        time.sleep(0.02)
    raise AssertionError("the command never ended")


def journaled(directory: Path) -> Iterator[tuple[str, str | None, str, dict[str, object]]]:
    for path in sorted(directory.glob("*.ndjson")):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if record.get("subject") == "Execution":
                yield record["key"], record["from"], record["to"], record["facts"]


def test_a_started_command_is_followed_to_its_end_with_its_log(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    context = start(runs)

    frames, result = follow(runs, context.attempt_id)

    assert frames == [
        LogFrame(stream="stdout", level="info", message="one"),
        LogFrame(stream="system", level="info", message="two"),
    ]
    assert result.status == "succeeded"
    assert result.context == context


def test_a_follow_starts_after_the_lines_its_caller_already_has(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    context = start(runs)

    frames, _ = follow(runs, context.attempt_id, after=1)

    assert frames == [LogFrame(stream="system", level="info", message="two")]


def test_a_follow_of_an_attempt_the_store_does_not_hold_is_refused(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    context = start(runs)
    with pytest.raises(UnknownExecutionError):
        runs.follow("ree", "never", 0)
    with pytest.raises(UnknownExecutionError):
        runs.follow("other-ree", context.attempt_id, 0)


def test_an_ree_runs_one_command_at_a_time(tmp_path: Path) -> None:
    runs = executions(tmp_path, f'while [ ! -e "{tmp_path / "marker"}" ]; do sleep 0.02; done', slots=2)
    first = start(runs)

    with pytest.raises(ReeBusyError):
        start(runs, run_id="run-2")
    other = start(runs, ree_id="ree-2")
    assert runs.holds("ree")
    assert runs.holds("ree-2")

    (tmp_path / "marker").touch()
    assert runs.wait(first.attempt_id, 10)
    assert runs.wait(other.attempt_id, 10)
    assert not runs.holds("ree")
    start(runs, run_id="run-3")


def test_a_command_waits_a_while_for_the_one_running_in_its_ree(tmp_path: Path) -> None:
    runs = executions(tmp_path, "sleep 0.3")
    first = start(runs)
    second = ExecutionContext.new()
    asyncio.run(runs.start("{}", "run-2", {}, second, ree_id="ree", wait=10))
    assert runs.wait(first.attempt_id, 0)
    assert runs.wait(second.attempt_id, 10)


def test_a_command_waits_for_a_free_slot(tmp_path: Path) -> None:
    runs = executions(tmp_path, f'while [ ! -e "{tmp_path / "marker"}" ]; do sleep 0.02; done')
    first = start(runs)

    second = ExecutionContext.new()

    async def start_second() -> bool:
        waiting = asyncio.ensure_future(runs.start("{}", "run-2", {}, second, ree_id="ree-2"))
        await asyncio.sleep(0.2)
        waited = not waiting.done()
        (tmp_path / "marker").touch()
        await asyncio.wait_for(waiting, 10)
        return waited

    assert asyncio.run(start_second())
    assert runs.wait(first.attempt_id, 10)
    assert runs.wait(second.attempt_id, 10)


def test_the_workbench_journals_each_executor_it_starts_and_how_it_ended(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    with store_journal(runs.directory.parent.parent, "lab-1") as directory:
        context = start(runs, dispatch_record="api-000001#7")
        assert runs.wait(context.attempt_id, 10)
    assert [entry for entry in journaled(directory) if entry[0] == context.attempt_id] == [
        (
            context.attempt_id,
            None,
            "started",
            {"operation": "lint_scripts", "run_id": "run-1", "dispatched_by": "api-000001#7"},
        ),
        (context.attempt_id, "started", "exited", {"status": "succeeded", "exit_code": 0}),
    ]


def cancellable(tmp_path: Path, on_term: str) -> str:
    """What ``execute`` does: wait for the cancel marker and report canceled, or report on SIGTERM, or neither."""
    marker = tmp_path / "marker"
    canceled = 'report() { echo \'{"status":"canceled"}\'; exit 0; }'
    if on_term == "cooperative":
        return f'{canceled}; while [ ! -e "{marker}" ]; do sleep 0.02; done; report'
    if on_term == "report":
        return f"{canceled}; trap report TERM; while :; do sleep 0.02; done"
    return "trap '' TERM; while :; do sleep 0.02; done"


@pytest.mark.parametrize("on_term", ["cooperative", "report", "ignore"])
def test_cancel_lets_the_executor_stop_itself_and_forces_only_one_that_does_not(tmp_path: Path, on_term: str) -> None:
    runs = executions(tmp_path, cancellable(tmp_path, on_term), cancel_grace=0.3, cancel_kill=0.3)
    with store_journal(runs.directory.parent.parent, "lab-1") as directory:
        context = start(runs)
        began = time.monotonic()
        runs.cancel("run-1", ree_id="ree", record="api-000001#9")
        runs.cancel("run-1", ree_id="ree", record="api-000001#10")
        assert time.monotonic() - began < 0.3, "cancel waits for the grace period instead of returning"
        _, result = follow(runs, context.attempt_id)
        assert runs.wait(context.attempt_id, 10)
    (_, _, target, facts) = list(journaled(directory))[-1]
    assert target == "stopped"
    assert facts["cause"] == "cancel"
    assert facts["canceled_by"] == "api-000001#9"
    if on_term == "ignore":
        # Killed, wrapper and all: it could not report, so core settled its attempt.
        assert facts["exit_code"] == -signal.SIGKILL
        assert facts["status"] == "interrupted"
        assert result.status == "failed"
    else:
        assert facts["status"] == "canceled"
        assert result.status == "canceled"


def launched(tmp_path: Path, runs: Executions, attempt_id: str, execute: str, ree_id: str = "ree") -> Identity:
    """An executor a previous workbench process of the store started, still running or not."""
    directory = runs.directory / attempt_id
    directory.mkdir(parents=True)
    (directory / "command.json").write_text("{}")
    script = tmp_path / f"{attempt_id}.sh"
    script.write_text(f"#!/bin/sh\ncat >/dev/null\necho line >&2\n{execute}\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    process = subprocess.Popen([*_WRAPPER, str(script)], cwd=directory, start_new_session=True)
    identity = Identity(
        attempt_id=attempt_id, ree_id=ree_id, run_id="run-1", operation="build_runtime", pid=process.pid
    )
    identity = identity.model_copy(update={"birth": _birth(process.pid)})
    (directory / "identity.json").write_text(identity.model_dump_json())
    return identity


def test_a_restarted_workbench_adopts_an_executor_still_running_and_sees_it_end(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    marker = tmp_path / "go"
    launched(tmp_path, runs, "a1", f'while [ ! -e "{marker}" ]; do sleep 0.02; done; echo \'{{"status":"succeeded"}}\'')
    time.sleep(0.2)

    with store_journal(runs.directory.parent.parent, "lab-1") as directory:
        assert runs.reconcile() == {"a1"}
        assert runs.holds("ree")
        marker.touch()
        frames, result = follow(runs, "a1")
        assert runs.wait("a1", 10)
    assert result.status == "succeeded"
    assert frames == [LogFrame(stream="system", level="info", message="line")]
    assert [(source, target) for _, source, target, _ in journaled(directory)] == [
        ("started", "adopted"),
        ("adopted", "exited"),
    ]
    assert json.loads((runs.directory / "a1" / "identity.json").read_text())["state"] == "adopted"


def test_an_executor_gone_without_reporting_is_lost_and_its_attempt_settled(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    identity = launched(tmp_path, runs, "a1", "sleep 30")
    time.sleep(0.2)
    os.killpg(identity.pid, signal.SIGKILL)
    time.sleep(0.2)

    with store_journal(runs.directory.parent.parent, "lab-1") as directory:
        assert runs.reconcile() == set()
    _, result = follow(runs, "a1")
    assert result.history is not None
    assert result.history.operation_status == "interrupted"
    assert list(journaled(directory)) == [
        ("a1", "started", "lost", {"status": "interrupted", "commit": "c" * 40, "record": None, "reason": "vanished"})
    ]
    assert not runs.holds("ree")


def test_an_executor_that_ended_while_no_workbench_ran_is_settled_as_it_ended(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    launched(tmp_path, runs, "a1", 'echo \'{"status":"canceled"}\'; exit 1')
    time.sleep(0.3)

    with store_journal(runs.directory.parent.parent, "lab-1") as directory:
        runs.reconcile()
    assert list(journaled(directory)) == [("a1", "started", "exited", {"status": "canceled", "exit_code": 1})]


def test_an_ending_not_journaled_before_a_crash_is_journaled_once_by_the_next_process(tmp_path: Path) -> None:
    runs = executions(tmp_path)
    launched(tmp_path, runs, "a1", 'echo \'{"status":"succeeded"}\'')
    time.sleep(0.3)
    with store_journal(runs.directory.parent.parent, "lab-1") as first:
        runs.reconcile()
    ending = json.loads((runs.directory / "a1" / "ending.json").read_text())
    (runs.directory / "a1" / "ending.json").write_text(json.dumps({**ending, "journaled": False}))

    again = Executions(runs._executor)
    with store_journal(runs.directory.parent.parent, "lab-1") as second:
        again.reconcile()
        again.reconcile()
    assert [target for _, _, target, _ in journaled(first)] == ["exited", "exited"]
    assert second == first
