"""Journals written by the runtime are read back with their completeness intact."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from repo2ree_assurance_checker.check import check
from repo2ree_assurance_checker.dossier import one_per_history
from repo2ree_assurance_checker.evidence import Evidence, Source
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.sources import (
    Commit,
    attempt_events,
    history_head,
    load_evidence,
    read_journals,
    recorded_phases,
)


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


def test_a_malformed_header_makes_a_journal_incomplete_instead_of_misread(tmp_path: Path) -> None:
    header = {"v": 1, "seq": 1, "kind": "journal.opened", "process": "api", "epoch": 1, "hosts": "api"}
    (tmp_path / "api-000001.ndjson").write_text(json.dumps(header) + "\n")
    (source,), _ = read_journals(tmp_path)
    assert not source.complete
    assert source.problems[0].startswith("seq 1: malformed journal.opened header")
    assert source.hosts == frozenset({"api"})  # The process itself, never the letters of a string.


RECORD: dict[str, object] = {
    "attempt_id": "a1",
    "context": {"ree_id": "ree-1", "dispatch_record": "api-000001#3"},
    "command": {"operation": "build_runtime"},
    "run_id": "build-1",
    "scope": ".",
    "operation_status": "succeeded",
    "capture_status": "captured",
}


def test_an_attempt_replays_the_phases_core_recorded_in_their_order() -> None:
    phases = ["pending", "executing", "completed", "capture_failed"]
    record = {**RECORD, "phases": phases, "capture_status": "failed"}
    events = attempt_events("git:ree", 10, record, None)
    assert [event.target_state for event in events] == phases
    assert events[0].facts["dispatched_by"] == "api-000001#3"
    assert recorded_phases(record, None) == (phases, None)


def test_a_skipped_phase_is_replayed_as_recorded_and_the_machine_refuses_it() -> None:
    record = {**RECORD, "phases": ["pending", "completed"], "capture_status": "pending"}
    events = attempt_events("git:ree", 10, record, None)
    assert [(event.source_state, event.target_state) for event in events] == [
        (None, "pending"),
        ("pending", "completed"),
    ]
    spec = load_spec()
    result = check(spec, Evidence(sources=(git_source(),), events=tuple(events)))
    (machine,) = [rule for rule in result.rules if rule.rule == "machine:Attempt"]
    assert [f.reason for f in machine.findings] == ["undeclared transition pending -> completed"]


def test_phases_that_disagree_with_the_record_or_are_missing_are_reported() -> None:
    _, disagree = recorded_phases({**RECORD, "phases": ["pending", "executing"], "capture_status": "failed"}, None)
    assert disagree == "attempt a1: recorded phases end in executing, but its record and commit say capture_failed"
    implied, missing = recorded_phases({**RECORD, "capture_status": "failed"}, None)
    assert implied == ["pending", "executing", "completed", "capture_failed"]
    assert missing == "attempt a1: no recorded phases; its transitions are inferred, not evidenced"


def git_source() -> Source:
    return Source(
        id="git:ree",
        kind="git",
        process="core",
        rank=0,
        hosts=frozenset({"core"}),
        complete=True,
        closed=False,
        partitions=frozenset({"ree-1"}),
    )


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
# Git histories are evidence under test: without git these tests would check nothing, so they fail rather than skip.
if GIT is None:
    raise RuntimeError("checker tests need a git executable: put git on PATH or set REPO2REE_TOOL_GIT")


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


GIT_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def captured_repository(root: Path, *attempts: str) -> list[str]:
    """An REE history with one capture commit per attempt; returns the commit ids."""
    assert GIT is not None
    environment = {**os.environ, **GIT_ENVIRONMENT}
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True, env=environment)
    commits: list[str] = []
    for attempt in attempts:
        record = {
            "attempt_id": attempt,
            "context": {"ree_id": "ree-1"},
            "command": {"operation": "x"},
            "operation_status": "succeeded",
        }
        message = "x\n\n" + json.dumps({"kind": "operation.completed", "schema_version": 2, "record": record})
        subprocess.run(
            [GIT, "-C", str(root), "commit", "-q", "--allow-empty", "-m", message], check=True, env=environment
        )
        head = subprocess.run([GIT, "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
        commits.append(head.stdout.strip())
    return commits


def test_a_downloaded_archive_is_read_through_its_exported_journal(tmp_path: Path) -> None:
    # An export checks out the seal and keeps the history it came from as imports/<tip>/journal.
    assert GIT is not None
    root = tmp_path / "ree"
    sealed, after_seal = captured_repository(root, "seal", "after-seal")
    subprocess.run(
        [GIT, "-C", str(root), "update-ref", f"refs/repo2ree/imports/{after_seal}/journal", after_seal], check=True
    )
    subprocess.run([GIT, "-C", str(root), "update-ref", "refs/heads/ree-history", sealed], check=True)
    other = captured_repository(tmp_path / "elsewhere", "elsewhere")[0]
    subprocess.run([GIT, "-C", str(root), "fetch", "-q", str(tmp_path / "elsewhere"), "ree-history"], check=True)
    subprocess.run([GIT, "-C", str(root), "update-ref", f"refs/repo2ree/imports/{other}/journal", other], check=True)

    assert history_head(GIT, root) == (f"refs/repo2ree/imports/{after_seal}/journal", [])
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    assert {event.key for event in evidence.events if event.subject == "Attempt"} == {"seal", "after-seal"}


def update_ref(root: Path, ref: str, commit: str) -> None:
    assert GIT is not None
    subprocess.run([GIT, "-C", str(root), "update-ref", ref, commit], check=True)


def loaded_repository(tmp_path: Path) -> tuple[Path, str, str, str]:
    """A reader's REE that loaded an author's bundle: (root, reader's initial, its load, the author's seal)."""
    assert GIT is not None
    author = tmp_path / "author"
    (sealed,) = captured_repository(author, "author-seal")
    root = tmp_path / "reader"
    initial, load = captured_repository(root, "reader-init", "reader-load")
    update_ref(root, "refs/repo2ree/initial", initial)
    # Loading keeps the head it replaced and fetches the bundle under its own namespace.
    update_ref(root, f"refs/repo2ree/imports/{initial}/journal", initial)
    subprocess.run(
        [GIT, "-C", str(root), "fetch", "-q", str(author), f"+refs/*:refs/repo2ree/imports/{sealed}/*"], check=True
    )
    return root, initial, load, sealed


def test_a_loaded_ree_in_its_workbench_is_read_through_ree_history(tmp_path: Path) -> None:
    assert GIT is not None
    root, _, _, _ = loaded_repository(tmp_path)
    assert history_head(GIT, root) == ("refs/heads/ree-history", [])


def test_a_downloaded_loaded_ree_is_read_through_its_own_journal_not_the_author_seal(tmp_path: Path) -> None:
    assert GIT is not None
    # Its export checks out the author's seal; the reader's initialization and load are on the journal ref.
    root, _, load, sealed = loaded_repository(tmp_path)
    update_ref(root, f"refs/repo2ree/imports/{load}/journal", load)
    update_ref(root, "refs/heads/ree-history", sealed)

    assert history_head(GIT, root) == (f"refs/repo2ree/imports/{load}/journal", [])
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    assert {event.key for event in evidence.events if event.subject == "Attempt"} == {"reader-init", "reader-load"}


def test_diverging_histories_from_the_initial_capture_are_reported(tmp_path: Path) -> None:
    assert GIT is not None
    root, initial, _, _ = loaded_repository(tmp_path)
    tree = subprocess.run([GIT, "-C", str(root), "rev-parse", f"{initial}^{{tree}}"], capture_output=True, text=True)
    sibling = subprocess.run(
        [GIT, "-C", str(root), "commit-tree", tree.stdout.strip(), "-p", initial, "-m", "elsewhere"],
        capture_output=True,
        text=True,
        env={**os.environ, **GIT_ENVIRONMENT},
        check=True,
    ).stdout.strip()
    update_ref(root, f"refs/repo2ree/imports/{sibling}/journal", sibling)
    head, problems = history_head(GIT, root)
    assert head == "refs/heads/ree-history"
    grown = ["refs/heads/ree-history", *(f"refs/repo2ree/imports/{commit}/journal" for commit in (initial, sibling))]
    assert problems == [f"cannot tell which history continues refs/repo2ree/initial: {sorted(grown)}"]


def test_a_workbench_repository_is_read_through_ree_history(tmp_path: Path) -> None:
    assert GIT is not None
    captured_repository(tmp_path / "ree", "a1")
    assert history_head(GIT, tmp_path / "ree") == ("refs/heads/ree-history", [])


def snapshot(label: str, *attempts: tuple[str, str | None]) -> Evidence:
    """One REE's history as a download holds it: each attempt, captured by a commit or still pending."""
    events = [
        event
        for index, (attempt, commit) in enumerate(attempts)
        for event in attempt_events(
            f"git:{label}",
            (index + 1) * 1000,
            {**RECORD, "attempt_id": attempt, "phases": ["pending", "executing", "completed", "captured"]},
            None if commit is None else Commit(commit, "t", None, "x", None),
        )
    ]
    source = git_source().model_copy(update={"id": f"git:{label}"})
    return Evidence(sources=(source,), events=tuple(events))


def test_snapshots_of_one_history_are_read_once_as_the_latest() -> None:
    before_seal = snapshot("early", ("a1", "c1"))
    after_seal = snapshot("late", ("a1", "c1"), ("a2", "c2"))
    kept, problems = one_per_history([before_seal, after_seal, after_seal.model_copy()])
    assert kept == [after_seal]
    assert problems == []


def test_snapshots_that_are_not_prefixes_of_the_latest_are_reported() -> None:
    rewritten = snapshot("early", ("a1", "c9"))
    kept, problems = one_per_history([rewritten, snapshot("late", ("a1", "c1"), ("a2", "c2"))])
    assert [evidence.sources[0].id for evidence in kept] == ["git:late"]
    assert problems == ["git:early is not a prefix of git:late: the snapshots diverge"]
