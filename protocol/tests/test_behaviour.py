"""The generated machines and the journal writer owners record through."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_protocol.allocation import AllocationState
from repo2ree_protocol.behaviour import MACHINES, SPEC_DIGEST, IllegalTransitionError, require_transition
from repo2ree_protocol.behaviour.writer import FileJournal, Journal, close_journal, journal, open_journal


def records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_allocation_states_are_the_specified_machine() -> None:
    assert MACHINES["Allocation"].states == tuple(state.value for state in AllocationState)


def test_require_transition_follows_the_specification() -> None:
    require_transition("Allocation", "requested", "provisioning")
    require_transition("Allocation", "released", "released")
    with pytest.raises(IllegalTransitionError, match="illegal allocation transition released -> assigned"):
        require_transition("Allocation", "released", "assigned")


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
    assert written[0]["spec_digest"] == SPEC_DIGEST
    assert written[0]["hosts"] == ["api", "supervisor"]
    assert written[1]["facts"] == {"status": "failed"}


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
