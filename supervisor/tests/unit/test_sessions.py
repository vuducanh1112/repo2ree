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

from repo2ree_protocol.command import BuildRuntimeCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame, ResultFrame
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_supervisor import (
    CommandDispatcher,
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
    with pytest.raises(WorkbenchUnavailableError, match="ended before the command was sent"):
        client.exec_action("wb-1", "{}", "run-1", {}, ree_id="ree-1", session=journaled)
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
        dispatcher.dispatch_action(handle, BuildRuntimeCommand(), "run-1", lambda *_: None)
    rows = [json.loads(line) for path in journal_dir.glob("*.ndjson") for line in path.read_text().splitlines()]
    assert not [row for row in rows if row.get("subject") == "dispatch"]


class _CancelledBench:
    """A workbench whose command runs until it is canceled, remembering what each cancel named."""

    def __init__(self) -> None:
        self.canceled = threading.Event()
        self.records: list[str | None] = []

    def session_of(self, workbench_id: str) -> str | None:
        return "s-1"

    def exec_action(
        self,
        workbench_id: str,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext | None = None,
        *,
        ree_id: str,
        session: str | None = None,
    ) -> Iterator[Frame]:
        self.canceled.wait(5)
        yield ResultFrame(result=ActionResult(status="canceled", context=context))

    def cancel_run(self, workbench_id: str, run_id: str, *, ree_id: str, record: str | None = None) -> None:
        self.records.append(record)
        self.canceled.set()


def test_a_cancel_of_a_command_in_flight_is_journaled_once_and_names_its_record(journal_dir: Path) -> None:
    bench = _CancelledBench()
    dispatcher = CommandDispatcher(bench, ReeLocks())  # type: ignore[arg-type]
    handle = ReeRoute(ree_id="ree-1", workbench_id="wb-1", store_id="lab-1")
    results: list[ActionResult] = []
    running = threading.Thread(
        target=lambda: results.append(
            dispatcher.dispatch_action(handle, BuildRuntimeCommand(), "run-1", lambda *_: None)
        )
    )
    running.start()
    while not dispatcher._dispatched:
        time.sleep(0.01)
    dispatcher.cancel_run(handle, "run-1")
    dispatcher.cancel_run(handle, "run-1")
    running.join(5)
    rows = [json.loads(line) for path in journal_dir.glob("*.ndjson") for line in path.read_text().splitlines()]
    cancels = [row for row in rows if row.get("subject") == "cancel_run"]
    assert [(row["kind"], row["message"]) for row in cancels] == [("send", "cancel_run"), ("receive", "done")]
    context = results[0].context
    assert context is not None
    assert cancels[0]["key"] == context.attempt_id
    assert cancels[0]["facts"] == {"run_id": "run-1", "session": "s-1"}
    assert bench.records == [f"api-000001#{cancels[0]['seq']}", None]
    assert not dispatcher._dispatched
