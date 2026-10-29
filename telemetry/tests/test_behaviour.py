"""The journal writer and the typed records owners write through it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from repo2ree_protocol.allocation import AllocationState
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
    events.author_api_action("a1", None, "requested", action="build_runtime", partition="ree-1", facts={"run_id": "r1"})
    events.author_api_action(
        "a1", "requested", "failed", action="build_runtime", partition="ree-1", facts={"failure_category": "x"}
    )
    events.allocation(
        "al1",
        None,
        AllocationState.REQUESTED,
        partition="ree-1",
        facts={"provider_id": "p", "workbench_id": "w", "location_id": None},
    )
    events.allocation(
        "al1", AllocationState.REQUESTED, AllocationState.FAILED, partition="ree-1", facts={"detail": "x"}
    )
    sent = events.dispatch_sent("a1", partition="ree-1", facts={"operation": "build_runtime", "run_id": "r1"})
    events.dispatch_received("a1", "result", partition="ree-1", facts={"status": "succeeded", "commit": "c" * 40})
    events.dispatch_sent("a2", partition="ree-1", facts={"operation": "build_runtime", "run_id": "r1"})
    events.dispatch_received("a2", "unavailable", partition="ree-1")
    events.dispatch_sent("a3", partition="ree-1", facts={"operation": "build_runtime", "run_id": "r1"})
    events.dispatch_abandoned("a3", partition="ree-1", reason="closed_without_response")
    close_journal(final=True)
    assert sent == "api-000001#6"
    checked = kept_contract(tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_without_an_open_journal_nothing_is_recorded() -> None:
    close_journal()
    assert type(journal()) is Journal
    journal().transition("api", "Run", "r", None, "queued", partition=None)


def test_a_journal_is_sequenced_stamped_and_closed(tmp_path: Path) -> None:
    opened = open_journal(tmp_path, "api", hosts=("supervisor",))
    journal().receive("supervisor", "dispatch", "result", "a1", partition="ree-1", facts={"status": "failed"})
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
