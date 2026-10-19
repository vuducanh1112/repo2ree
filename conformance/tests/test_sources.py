"""Journals written by the runtime are read back with their completeness intact."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_conformance.sources import attempt_events, load_evidence, read_journals, recording_inputs
from repo2ree_protocol.behaviour import close_journal, journal, open_journal


def write_journal(directory: Path) -> Path:
    opened = open_journal(directory, "api", hosts=("api", "supervisor"))
    journal().transition("api", "Run", "run-1", None, "queued", partition="ree-1", facts={"operation": "build"})
    journal().send("supervisor", "dispatch", "exec_action", "a1", partition="ree-1", facts={"operation": "x"})
    journal().abandon("supervisor", "dispatch", "a1", partition="ree-1", reason="TimeoutError")
    close_journal()
    return opened.path


def test_runtime_journals_round_trip(tmp_path: Path) -> None:
    write_journal(tmp_path)
    sources, events = read_journals(tmp_path)
    assert [(source.id, source.complete, source.closed) for source in sources] == [("api-000001", True, True)]
    assert sources[0].hosts == {"api", "supervisor"}
    assert [(event.kind, event.subject, event.position) for event in events] == [
        ("transition", "Run", 2),
        ("send", "dispatch", 3),
        ("abandon", "dispatch", 4),
    ]
    assert events[2].facts == {"reason": "TimeoutError"}


def test_journal_records_keep_the_span_they_were_written_in(tmp_path: Path) -> None:
    records = [
        {"v": 1, "seq": 1, "kind": "journal.opened", "process": "api", "epoch": 1, "hosts": ["api"]},
        {
            "v": 1,
            "seq": 2,
            "kind": "transition",
            "owner": "api",
            "subject": "Run",
            "key": "run-1",
            "partition": "ree-1",
            "from": None,
            "to": "queued",
            "trace": {"trace_id": "a" * 32, "span_id": "b" * 16},
        },
        {"v": 1, "seq": 3, "kind": "transition", "owner": "api", "subject": "Run", "key": "run-1", "to": "running"},
        {
            "v": 1,
            "seq": 4,
            "kind": "transition",
            "owner": "api",
            "subject": "Run",
            "key": "run-1",
            "from": "running",
            "to": "succeeded",
            "trace": {"trace_id": 7, "span_id": None},
        },
    ]
    (tmp_path / "api-000001.ndjson").write_text("".join(json.dumps(record) + "\n" for record in records))
    sources, events = read_journals(tmp_path)
    assert [(event.trace_id, event.span_id) for event in events] == [("a" * 32, "b" * 16), (None, None), (None, None)]
    # Context only: a malformed one never makes the journal incomplete.
    assert sources[0].complete, sources[0].problems


def test_each_process_start_is_a_new_epoch(tmp_path: Path) -> None:
    write_journal(tmp_path)
    write_journal(tmp_path)
    sources, _ = read_journals(tmp_path)
    assert [(source.id, source.rank) for source in sources] == [("api-000001", 1), ("api-000002", 2)]


def test_lost_and_torn_records_make_a_journal_incomplete(tmp_path: Path) -> None:
    path = write_journal(tmp_path)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], *lines[2:]]) + "\n" + '{"seq": 6, "kind": "tran')
    (source,), _ = read_journals(tmp_path)
    assert not source.complete
    assert source.problems[0] == "sequence jumps from 1 to 3"
    assert source.problems[1].startswith("line 5: torn final record")


def test_a_missing_earlier_epoch_taints_the_later_one(tmp_path: Path) -> None:
    write_journal(tmp_path)
    write_journal(tmp_path)
    (tmp_path / "api-000001.ndjson").unlink()
    (source,), _ = read_journals(tmp_path)
    assert source.problems == ("an earlier epoch of this process is missing",)


def test_an_unclosed_journal_is_complete_but_open(tmp_path: Path) -> None:
    open_journal(tmp_path, "api")
    journal().transition("api", "Run", "run-1", None, "queued", partition="ree-1", facts={})
    try:
        (source,), _ = read_journals(tmp_path)
        assert source.complete
        assert not source.closed
    finally:
        close_journal()


def test_attempt_records_become_their_proven_transitions() -> None:
    record = {
        "attempt_id": "a1",
        "context": {"ree_id": "ree-1"},
        "command": {"operation": "seal_ree"},
        "run_id": "seal-1",
        "scope": ".",
        "operation_status": "succeeded",
        "capture_status": "failed",
        "capture_error": "disk full",
    }
    events = attempt_events("git:ree", 10, record, None)
    assert [(event.source_state, event.target_state) for event in events] == [
        (None, "pending"),
        ("pending", "executing"),
        ("executing", "completed"),
        ("completed", "capture_failed"),
    ]
    not_started = attempt_events("git:ree", 10, {**record, "operation_status": "not_started"}, None)
    assert [event.target_state for event in not_started] == ["pending", "capture_failed"]
    pending = attempt_events(
        "git:ree", 10, {**record, "operation_status": "unknown", "capture_status": "pending"}, None
    )
    assert [event.target_state for event in pending] == ["pending", "executing"]


GIT = os.environ.get("REPO2REE_TOOL_GIT") or shutil.which("git")


@pytest.mark.skipif(GIT is None, reason="needs a git executable")
def test_unreadable_capture_commits_make_git_evidence_incomplete(tmp_path: Path) -> None:
    assert GIT is not None
    root = tmp_path / "ree"
    root.mkdir()
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True, env=environment)
    record = {
        "attempt_id": "a1",
        "context": {"ree_id": "ree-1"},
        "command": {"operation": "x"},
        "operation_status": "succeeded",
        "changed": False,
    }
    for message in (
        "x\n\n" + json.dumps({"kind": "operation.completed", "schema_version": 2, "record": record}),
        "y\n\nnot json",
    ):
        subprocess.run(
            [GIT, "-C", str(root), "commit", "-q", "--allow-empty", "-m", message], check=True, env=environment
        )
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    (source,) = evidence.sources
    assert source.partitions == frozenset({"ree-1"})
    assert [event.target_state for event in evidence.events] == ["pending", "executing", "completed", "captured"]
    assert not source.complete
    assert "commit without readable capture metadata" in source.problems[0]


def test_recordings_are_discovered_by_layout(tmp_path: Path) -> None:
    (tmp_path / "journal").mkdir()
    (tmp_path / "capture" / "rees" / "workbench" / ".git").mkdir(parents=True)
    (tmp_path / "capture" / "rees" / "not-a-repo").mkdir()
    (tmp_path / "stores").mkdir()
    journals, repositories, stores = recording_inputs(tmp_path)
    assert journals == [tmp_path / "journal"]
    assert repositories == [tmp_path / "capture" / "rees" / "workbench"]
    assert stores == [tmp_path / "stores"]
