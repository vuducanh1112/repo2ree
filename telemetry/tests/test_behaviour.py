"""The journal writer and the typed records owners write through it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from repo2ree_telemetry.behaviour import VOCABULARY, events
from repo2ree_telemetry.behaviour.writer import FileJournal, Journal, close_journal, journal, open_journal


def records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def kept_contract(journals: Path) -> subprocess.CompletedProcess[str]:
    """What the published contract's own checker says about the journals written here."""
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "validate-journal", str(journals)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_every_typed_record_keeps_the_published_contract(tmp_path: Path) -> None:
    open_journal(tmp_path, "api", hosts=("supervisor",))
    events.author_api_action(
        "a1", None, "requested", action="build_experiment_environment", partition="ree-1", facts={"run_id": "r1"}
    )
    events.author_api_action(
        "a1",
        "requested",
        "failed",
        action="build_experiment_environment",
        partition="ree-1",
        facts={"failure_category": "x"},
    )
    sent = events.start_run_sent(
        "a1", partition="ree-1", facts={"operation": "build_experiment_environment", "run_id": "r1", "session": "s1"}
    )
    events.start_run_received("a1", "accepted", partition="ree-1")
    events.follow_run_sent("a1", partition="ree-1", facts={"run_id": "r1", "session": "s1"})
    events.follow_run_abandoned("a1", partition="ree-1", reason="session_lost")
    events.follow_run_sent("a1", partition="ree-1", facts={"run_id": "r1", "session": "s2"})
    events.follow_run_received("a1", "settled", partition="ree-1", facts={"status": "succeeded", "commit": "c" * 40})
    events.start_run_sent(
        "a2", partition="ree-1", facts={"operation": "build_experiment_environment", "run_id": "r1", "session": "s1"}
    )
    events.start_run_received("a2", "busy", partition="ree-1")
    events.start_run_sent(
        "a3", partition="ree-1", facts={"operation": "build_experiment_environment", "run_id": "r1", "session": "s1"}
    )
    events.start_run_abandoned("a3", partition="ree-1", reason="closed_without_response")
    events.follow_run_sent("a4", partition="ree-1", facts={"run_id": "r4", "session": "s1"})
    events.follow_run_received("a4", "unknown", partition="ree-1")
    close_journal(final=True)
    assert sent == "api-000001#4"
    checked = kept_contract(tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_a_workbench_journal_and_its_references_are_named_by_its_store(tmp_path: Path) -> None:
    opened = open_journal(tmp_path, "workbench", instance="store-1")
    events.execution(
        "a1",
        None,
        "started",
        partition="ree-1",
        facts={"operation": "build_experiment_environment", "run_id": "r1", "dispatched_by": "api-000001#4"},
    )
    events.execution(
        "a1", "started", "stopped", partition="ree-1", facts={"exit_code": 1, "cause": "cancel", "status": "canceled"}
    )
    events.execution("a2", None, "started", partition="ree-1", facts={"operation": "lint_scripts", "run_id": "r2"})
    events.execution("a2", "started", "adopted", partition="ree-1", facts={})
    events.execution(
        "a2", "adopted", "lost", partition="ree-1", facts={"status": "interrupted", "reason": "vanished", "commit": "c"}
    )
    reference = journal().send("workbench", "own", "asked", "a3", partition="ree-1")
    close_journal()
    checked = kept_contract(tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert reference == "store-1/workbench-000001#7"
    assert opened.id == "store-1/workbench-000001"
    assert records(opened.path)[0]["instance"] == "store-1"
    assert records(opened.path)[0]["hosts"] == ["workbench"]


def test_a_cancel_keeps_the_published_contract(tmp_path: Path) -> None:
    open_journal(tmp_path, "api", hosts=("supervisor",))
    sent = events.cancel_run_sent("a1", partition="ree-1", facts={"run_id": "r1", "session": "s1"})
    events.cancel_run_received("a1", "done", partition="ree-1")
    events.cancel_run_sent("a2", partition="ree-1", facts={"run_id": "r2", "session": "s1"})
    events.cancel_run_abandoned("a2", partition="ree-1", reason="TimeoutError")
    close_journal()
    assert sent == "api-000001#2"
    checked = kept_contract(tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_without_an_open_journal_nothing_is_recorded() -> None:
    close_journal()
    assert type(journal()) is Journal
    journal().transition("api", "Run", "r", None, "queued", partition=None)


def test_a_journal_is_sequenced_stamped_and_closed(tmp_path: Path) -> None:
    opened = open_journal(tmp_path, "api", hosts=("supervisor",))
    journal().receive("supervisor", "follow_run", "settled", "a1", partition="ree-1", facts={"status": "failed"})
    close_journal()
    written = records(opened.path)
    assert [(record["seq"], record["kind"]) for record in written] == [
        (1, "journal.opened"),
        (2, "receive"),
        (3, "journal.closed"),
    ]
    assert written[0]["vocabulary"] == VOCABULARY
    assert written[0]["hosts"] == ["api", "supervisor"]
    assert written[1]["facts"] == {"status": "failed"}


def test_a_final_close_says_so_and_an_ordinary_one_does_not(tmp_path: Path) -> None:
    ordinary = open_journal(tmp_path / "ordinary", "api")
    close_journal()
    final = open_journal(tmp_path / "final", "api")
    close_journal(final=True)
    assert records(ordinary.path)[-1]["kind"] == "journal.closed"
    assert "final" not in records(ordinary.path)[-1]
    assert (records(final.path)[-1]["kind"], records(final.path)[-1]["final"]) == ("journal.closed", True)


def test_a_failed_write_leaves_a_visible_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    writer = FileJournal(tmp_path, "api", ())
    original = writer._stream.write
    calls = {"count": 0}

    def flaky(text: str) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("disk full")
        return original(text)

    monkeypatch.setattr(writer._stream, "write", flaky)
    writer.transition("api", "Run", "r", None, "queued", partition="p")
    writer.transition("api", "Run", "r", "queued", "running", partition="p")
    writer.close()
    assert [record["seq"] for record in records(writer.path)] == [1, 3, 4]


def test_concurrent_processes_never_share_an_epoch(tmp_path: Path) -> None:
    first = FileJournal(tmp_path, "api", ())
    second = FileJournal(tmp_path, "api", ())
    assert (first.epoch, second.epoch) == (1, 2)
    first.close()
    second.close()
