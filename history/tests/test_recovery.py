"""Damaged evidence stays inspectable without destroying healthy observations."""

import json

import pytest
from history.tests.test_assembly import recording, span

from repo2ree_history.core.evidence import AssemblyResult, Diagnostic
from repo2ree_history.core.models import RecordLocator, SpanLocator
from repo2ree_history.shell.cli import main
from repo2ree_history.shell.recording import assemble_recording


def test_corrupt_lines_and_truncated_tail_preserve_healthy_records(tmp_path):
    root = recording(tmp_path)
    first, last = span(), span(2)
    (root / "traces.ndjson").write_bytes(
        json.dumps(first).encode() + b'\n{"context":\n' + json.dumps(last).encode() + b'\n\xff\n{"name":'
    )
    result = assemble_recording(root)
    assert len(result.events) == 6
    errors = [d for d in result.diagnostics if d.code == "malformed_record"]
    assert [ref.locator.line for d in errors for ref in d.source_refs if isinstance(ref.locator, RecordLocator)] == [
        2,
        4,
        5,
    ]
    assert all(d.severity == "invalid" for d in errors)
    assert len(result.unassigned) == 3
    output = tmp_path / "out"
    assert main(["assemble", str(root), "-o", str(output), "--strict"]) == 1
    saved = AssemblyResult.model_validate_json((output / "assembly.json").read_text())
    assert saved.events == result.events
    assert (output / "evidence-report.md").exists()


@pytest.mark.parametrize("mutation", ["missing_context", "missing_name", "bad_exit", "bad_state", "bad_commit"])
def test_record_schema_errors_do_not_abort_assembly(tmp_path, mutation):
    broken = span(2)
    states = []
    if mutation == "missing_context":
        del broken["context"]
    elif mutation == "missing_name":
        del broken["name"]
    elif mutation == "bad_exit":
        broken["attributes"]["repo2ree.exit_code"] = "not-a-number"
    elif mutation == "bad_commit":
        broken["attributes"]["repo2ree.history.before_snapshot_id"] = 42
    else:
        states = [{"state": "bad"}]
    result = assemble_recording(recording(tmp_path, [span(), broken], states))
    assert len(result.events) >= 3
    assert any(d.severity == "invalid" for d in result.diagnostics)


def test_identical_duplicate_is_info_and_missing_evidence_is_incomplete(tmp_path):
    root = recording(tmp_path, [span(), span()])
    result = assemble_recording(root)
    assert next(d for d in result.diagnostics if d.code == "duplicate_span").severity == "info"
    assert next(d for d in result.diagnostics if d.code == "producer_order_unknown").severity == "incomplete"
    assert main(["assemble", str(root), "-o", str(tmp_path / "out"), "--strict"]) == 0


def test_conflicting_duplicate_is_invalid_and_keeps_source(tmp_path):
    first, conflicting = span(), span()
    conflicting["name"] = "different"
    result = assemble_recording(recording(tmp_path, [first, conflicting]))
    issue = next(d for d in result.diagnostics if d.code == "conflicting_span")
    assert issue.severity == "invalid"
    assert isinstance(issue.source_refs[0].locator, SpanLocator)
    assert issue.source_refs[0].locator.line == 2
    assert any(item.reason == "conflicting_span" for item in result.unassigned)


def test_git_metadata_recovery_keeps_neighbors_and_pending_files(tmp_path, monkeypatch):
    from repo2ree_history.shell.git import read_operations

    root = tmp_path / "ree"
    pending = root / ".git/repo2ree/operations"
    pending.mkdir(parents=True)
    (pending / "bad.json").write_text('{"attempt_id":')
    (pending / "good.json").write_text('{"attempt_id":"pending"}')
    metadata = json.dumps({"schema_version": 2, "kind": "operation.completed", "record": {"attempt_id": "published"}})
    log = "a" * 40 + "\0build\n\n{broken\0" + "b" * 40 + "\0build\n\n" + metadata + "\0"

    def git(_repository, *args):
        return "refs/heads/ree-history\n" if args[0] == "for-each-ref" else log

    monkeypatch.setattr("repo2ree_history.shell.git.git", git)
    diagnostics: list[Diagnostic] = []
    rows = list(read_operations(tmp_path, "ree", "repo", diagnostics))
    assert {row[0]["attempt_id"] for row in rows} == {"published", "pending"}
    assert len(diagnostics) == 2
    assert all(d.code == "malformed_git_metadata" and d.severity == "invalid" for d in diagnostics)
    assert all(d.source_refs for d in diagnostics)
