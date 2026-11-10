"""A workbench's connection as the journal records it: one WorkbenchSession per socket."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from repo2ree_protocol.command import BuildExperimentEnvironmentCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import (
    AcceptedFrame,
    BusyFrame,
    Frame,
    LogFrame,
    ResultFrame,
    UnavailableFrame,
    UnknownFrame,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_supervisor import (
    CommandDispatcher,
    FollowStoppedError,
    ReeBusyError,
    ReeLocks,
    ReeRoute,
    WorkbenchConnection,
    WorkbenchConnectionRegistry,
    WorkbenchUnavailableError,
)
from repo2ree_supervisor.sessions import Session
from repo2ree_supervisor.workbench_link import WsWorkbenchClient
from repo2ree_telemetry.behaviour import close_journal, open_journal


@pytest.fixture
def journal_dir(tmp_path: Path) -> Iterator[Path]:
    open_journal(tmp_path, "api", hosts=("api", "supervisor"))
    yield tmp_path
    close_journal()


def sessions(directory: Path) -> list[tuple[str, str | None, str, dict[str, Any], str | None]]:
    """Every WorkbenchSession transition written so far: key, from, to, facts, partition."""
    rows = [json.loads(line) for path in sorted(directory.glob("*.ndjson")) for line in path.read_text().splitlines()]
    return [
        (row["key"], row["from"], row["to"], row["facts"], row["partition"])
        for row in rows
        if row.get("subject") == "WorkbenchSession"
    ]


def hello(workbench_id: str = "wb-1", nonce: str = "n-1", store_id: str = "lab-1") -> WorkbenchHello:
    return WorkbenchHello(workbench_id=workbench_id, nonce=nonce, store_id=store_id, version="1.2.3", slots=2)


def admitted(registry: WorkbenchConnectionRegistry, said: WorkbenchHello) -> WorkbenchConnection:
    """A connection admitted the way the connect route admits one."""
    session = Session(said, registered=True)
    connection = WorkbenchConnection(send_text=lambda _text: None, hello=said, session=session)
    registry.register(said.workbench_id, connection)
    session.connect()
    return connection


def test_a_session_is_opened_connected_and_lost_once(journal_dir: Path) -> None:
    connection = admitted(WorkbenchConnectionRegistry(), hello())
    connection.close("closed", 1006)
    connection.close("send_failed")
    moves = sessions(journal_dir)
    assert [(current, target) for _, current, target, _, _ in moves] == [
        (None, "opened"),
        ("opened", "connected"),
        ("connected", "lost"),
    ]
    assert {key for key, *_ in moves} == {connection.session_id}
    assert {partition for *_, partition in moves} == {"lab-1"}
    assert moves[1][3] == {
        "workbench_id": "wb-1",
        "nonce": "n-1",
        "store_id": "lab-1",
        "backend": "host",
        "slots": 2,
        "version": "1.2.3",
    }
    assert (moves[2][3]["reason"], moves[2][3]["close_code"]) == ("closed", 1006)


def test_a_refused_hello_for_an_unregistered_store_is_in_no_stores_history(journal_dir: Path) -> None:
    session = Session(hello(store_id="nobody"), registered=False)
    session.refuse("bad_token")
    session.lose("closed")
    assert [(target, facts.get("reason"), partition) for _, _, target, facts, partition in sessions(journal_dir)] == [
        ("opened", None, None),
        ("refused", "bad_token", None),
    ]


def test_a_reconnecting_workbench_supersedes_its_old_session(journal_dir: Path) -> None:
    registry = WorkbenchConnectionRegistry()
    old = admitted(registry, hello())
    new = admitted(registry, hello())
    lost = [(key, facts["reason"]) for key, _, target, facts, _ in sessions(journal_dir) if target == "lost"]
    assert lost == [(old.session_id, "superseded")]
    # The old socket ending afterwards records nothing more, and does not evict its successor.
    old.close("closed", 1000)
    registry.unregister("wb-1", old)
    assert len([row for row in sessions(journal_dir) if row[2] == "lost"]) == 1
    assert WsWorkbenchClient(registry).session_of("wb-1") == new.session_id


def test_a_control_plane_going_down_ends_every_session_as_shutdown(journal_dir: Path) -> None:
    registry = WorkbenchConnectionRegistry()
    admitted(registry, hello("wb-1", store_id="lab-1"))
    admitted(registry, hello("wb-2", nonce="n-2", store_id="lab-2"))
    registry.close_all("shutdown")
    assert sorted(facts["reason"] for _, _, target, facts, _ in sessions(journal_dir) if target == "lost") == [
        "shutdown",
        "shutdown",
    ]


def test_a_command_goes_on_the_session_it_was_journaled_for_or_not_at_all(journal_dir: Path) -> None:
    registry = WorkbenchConnectionRegistry()
    client = WsWorkbenchClient(registry)
    old = admitted(registry, hello())
    journaled = client.session_of("wb-1")
    assert journaled == old.session_id
    admitted(registry, hello())
    with pytest.raises(WorkbenchUnavailableError, match="ended before the request was sent"):
        client.start_run("wb-1", "{}", "run-1", {}, ExecutionContext.new(), ree_id="ree-1", session=journaled)
    assert client.session_of("nobody") is None


def test_every_session_record_keeps_the_published_contract(tmp_path: Path) -> None:
    open_journal(tmp_path, "api", hosts=("api", "supervisor"))
    registry = WorkbenchConnectionRegistry()
    admitted(registry, hello())
    Session(hello("wb-2", store_id="lab-1"), registered=True).refuse("store_claimed")
    Session(hello("wb-3", store_id="nobody"), registered=False).refuse("bad_token")
    registry.close_all("shutdown")
    close_journal(final=True)
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "validate-journal", str(tmp_path)]
    checked = subprocess.run(command, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_a_command_for_a_workbench_with_no_session_is_neither_journaled_nor_sent(journal_dir: Path) -> None:
    dispatcher = CommandDispatcher(WsWorkbenchClient(WorkbenchConnectionRegistry()), ReeLocks())
    handle = ReeRoute(ree_id="ree-1", workbench_id="wb-gone", store_id="lab-1")
    with pytest.raises(WorkbenchUnavailableError, match="not connected"):
        dispatcher.dispatch_action(handle, BuildExperimentEnvironmentCommand(), "run-1", lambda *_: None)
    rows = [json.loads(line) for path in journal_dir.glob("*.ndjson") for line in path.read_text().splitlines()]
    assert not [row for row in rows if row.get("subject") == "start_run"]


class _Bench:
    """A workbench whose command runs until it is canceled, or ``ends``; its sessions end when ``drop`` says."""

    def __init__(self, answer: Frame | None = None) -> None:
        self.answer = answer or AcceptedFrame()
        self.ends = threading.Event()
        self.records: list[str | None] = []
        self.follows: list[tuple[str, int]] = []
        self.drop = 0
        self.session = "s-1"
        self.result = ActionResult(status="canceled")

    def session_of(self, workbench_id: str) -> str | None:
        return self.session

    def start_run(
        self,
        workbench_id: str,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext,
        *,
        ree_id: str,
        session: str | None = None,
        wait: float = 0.0,
    ) -> Iterator[Frame]:
        self.context = context
        self.wait = wait
        yield self.answer

    def follow_run(
        self, workbench_id: str, attempt_id: str, after: int, *, ree_id: str, session: str | None = None
    ) -> Iterator[Frame]:
        self.follows.append((str(session), after))
        yield LogFrame(stream="stdout", level="info", message="line")
        if self.drop:
            self.drop -= 1
            self.session = f"s-{len(self.follows) + 1}"
            yield UnavailableFrame(detail="workbench connection closed")
            return
        if attempt_id == "unknown":
            yield UnknownFrame(detail="no such run")
            return
        self.ends.wait(5)
        yield ResultFrame(result=self.result.model_copy(update={"context": self.context}))

    def cancel_run(self, workbench_id: str, run_id: str, *, ree_id: str, record: str | None = None) -> None:
        self.records.append(record)
        self.ends.set()


HANDLE = ReeRoute(ree_id="ree-1", workbench_id="wb-1", store_id="lab-1")


def journaled(journal_dir: Path, subject: str) -> list[dict[str, Any]]:
    rows = [json.loads(line) for path in journal_dir.glob("*.ndjson") for line in path.read_text().splitlines()]
    return [row for row in rows if row.get("subject") == subject]


def test_a_cancel_of_a_command_in_flight_is_journaled_once_and_names_its_record(journal_dir: Path) -> None:
    bench = _Bench()
    dispatcher = CommandDispatcher(bench, ReeLocks())  # type: ignore[arg-type]
    results: list[ActionResult] = []
    running = threading.Thread(
        target=lambda: results.append(
            dispatcher.dispatch_action(HANDLE, BuildExperimentEnvironmentCommand(), "run-1", lambda *_: None)
        )
    )
    running.start()
    while not dispatcher._followed:
        time.sleep(0.01)
    dispatcher.cancel_run(HANDLE, "run-1")
    dispatcher.cancel_run(HANDLE, "run-1")
    running.join(5)
    cancels = journaled(journal_dir, "cancel_run")
    assert [(row["kind"], row["message"]) for row in cancels] == [("send", "cancel_run"), ("receive", "done")]
    context = results[0].context
    assert context is not None
    assert cancels[0]["key"] == context.attempt_id
    assert cancels[0]["facts"] == {"run_id": "run-1", "session": "s-1"}
    assert bench.records == [f"api-000001#{cancels[0]['seq']}", None]
    assert not dispatcher._followed


def test_a_command_is_followed_across_sessions_from_the_line_it_had_reached(journal_dir: Path) -> None:
    bench = _Bench()
    bench.drop = 2
    bench.result = ActionResult(status="succeeded")
    bench.ends.set()
    dispatcher = CommandDispatcher(bench, ReeLocks())  # type: ignore[arg-type]
    lines: list[str] = []
    progress: list[int] = []
    started: list[ExecutionContext] = []

    result = dispatcher.dispatch_action(
        HANDLE,
        BuildExperimentEnvironmentCommand(),
        "run-1",
        lambda stream, level, message: lines.append(message),
        on_started=started.append,
        on_progress=progress.append,
    )

    assert result.status == "succeeded"
    assert result.context == started[0]
    assert started[0].dispatch_record is not None
    assert bench.follows == [("s-1", 0), ("s-2", 1), ("s-3", 2)]
    assert lines == ["line", "line", "line"]
    assert progress[-1] == 3
    starts = journaled(journal_dir, "start_run")
    assert [(row["kind"], row["message"]) for row in starts] == [("send", "start_run"), ("receive", "accepted")]
    follows = journaled(journal_dir, "follow_run")
    assert [row["kind"] for row in follows] == ["send", "abandon", "send", "abandon", "send", "receive"]
    assert follows[-1]["facts"] == {"status": "succeeded", "commit": None, "record": None}


def test_a_busy_ree_refuses_the_command(journal_dir: Path) -> None:
    dispatcher = CommandDispatcher(_Bench(BusyFrame(detail="REE 'ree-1' has a run in progress")), ReeLocks())  # type: ignore[arg-type]
    with pytest.raises(ReeBusyError, match="in progress"):
        dispatcher.dispatch_action(HANDLE, BuildExperimentEnvironmentCommand(), "run-1", lambda *_: None)
    starts = journaled(journal_dir, "start_run")
    assert [(row["kind"], row["message"]) for row in starts] == [("send", "start_run"), ("receive", "busy")]


def test_a_command_the_workbench_does_not_know_fails(journal_dir: Path) -> None:
    dispatcher = CommandDispatcher(_Bench(), ReeLocks())  # type: ignore[arg-type]
    context = ExecutionContext.new(ree_id="ree-1").model_copy(update={"attempt_id": "unknown"})
    result = dispatcher.follow(HANDLE, context, "run-1", lambda *_: None)
    assert result.status == "failed"
    assert [row["message"] for row in journaled(journal_dir, "follow_run")] == ["follow_run", "unknown"]


def test_a_stopped_follower_leaves_the_command_running(journal_dir: Path) -> None:
    bench = _Bench()
    bench.session = None  # type: ignore[assignment]
    stop = threading.Event()
    stop.set()
    dispatcher = CommandDispatcher(bench, ReeLocks())  # type: ignore[arg-type]
    with pytest.raises(FollowStoppedError):
        dispatcher.follow(HANDLE, ExecutionContext.new(ree_id="ree-1"), "run-1", lambda *_: None, stop=stop)


def test_a_command_whose_workbench_does_not_come_back_is_given_up(journal_dir: Path) -> None:
    bench = _Bench()
    bench.session = None  # type: ignore[assignment]
    dispatcher = CommandDispatcher(bench, ReeLocks())  # type: ignore[arg-type]
    with pytest.raises(WorkbenchUnavailableError, match="did not come back"):
        dispatcher.follow(HANDLE, ExecutionContext.new(ree_id="ree-1"), "run-1", lambda *_: None, reconnect_timeout=0.0)
