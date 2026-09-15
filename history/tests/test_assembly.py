import json

from repo2ree_history.core.models import CommitLocator, RecordLocator, SourceReference, SpanLocator
from repo2ree_history.core.sequence import render_sequence
from repo2ree_history.core.validation import validate_execution
from repo2ree_history.shell.outputs import write_outputs
from repo2ree_history.shell.recording import assemble_recording


def recording(tmp_path, spans=(), states=()):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": "test-invocation",
                "nodeid": "test_pipeline",
                "started": 1,
                "finished": 2,
                "repositories": [],
            }
        )
    )
    for name, values in (("traces", spans), ("state", states)):
        (tmp_path / (name + ".ndjson")).write_text("\n".join(json.dumps(v) for v in values))
    return tmp_path


def span(number=1, workbench="wb", operation=True):
    attrs = {"repo2ree.workbench_id": workbench} if workbench else {}
    if operation:
        attrs.update(
            {
                "repo2ree.operation_id": "op",
                "repo2ree.attempt_id": "attempt",
                "repo2ree.operation": "build",
                "repo2ree.run_id": "run",
                "repo2ree.status": "succeeded",
            }
        )
    return {
        "name": "command.build",
        "context": {"trace_id": "0x" + "1" * 32, "span_id": f"0x{number:016x}"},
        "attributes": attrs,
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-01-01T00:00:01Z",
        "status": {},
        "links": [],
        "resource": {"attributes": {"service.name": "repo2ree-exec"}},
    }


def state():
    return {
        "index": 0,
        "label": "built",
        "state": {"ree_id": "ree", "workbench": {"workbench_id": "wb"}, "audit": {"build": {"receipt_run_id": "run"}}},
    }


def test_real_identity_join_without_fabricated_order_or_time(tmp_path):
    result = assemble_recording(recording(tmp_path, [span()], [state()]))
    (execution,) = result.executions
    assert len(execution.events) == 4
    assert all(e.sequence is None and e.producer.epoch is None for e in execution.events)
    observation = next(e for e in execution.events if e.payload.kind == "state.observed")
    assert observation.observed_at is None
    assert isinstance(observation.source_refs[0].locator, RecordLocator)
    assert observation.source_refs[0].locator.line == 1
    assert any(c.kind == "run" and c.value == "run" for c in result.correlations)
    completed = next(e for e in execution.events if e.payload.kind == "operation.completed")
    assert len(completed.causes) == 1
    assert not observation.causes
    assert {i.code for i in validate_execution(execution)} >= {
        "producer_order_unknown",
        "missing_execution_start",
        "missing_execution_end",
    }
    assert "INCOMPLETE" in render_sequence(execution)


def test_conflicting_attempt_preserves_explicit_workbenches(tmp_path):
    result = assemble_recording(recording(tmp_path, [span(workbench="one"), span(2, "two")]))
    assert len(result.executions) == 2
    assert any(d.code == "identity_conflict" and d.severity == "invalid" for d in result.diagnostics)


def test_shared_ree_and_time_do_not_assign_lifecycle(tmp_path):
    isolated = span(workbench=None, operation=False)
    isolated["attributes"]["repo2ree.ree_id"] = "ree"
    result = assemble_recording(recording(tmp_path, [isolated], [state()]))
    assert not result.unassigned
    assert len(result.ree_histories[0].event_ids) == 2
    assert len(result.executions[0].events) == 1


def test_duplicate_export_keeps_both_locations_without_duplicate_events(tmp_path):
    s = span()
    result = assemble_recording(recording(tmp_path, [s, s]))
    assert len(result.executions[0].events) == 3
    assert {
        r.locator.line for r in result.executions[0].events[0].source_refs if isinstance(r.locator, SpanLocator)
    } == {1, 2}
    assert any(d.code == "duplicate_span" for d in result.diagnostics)


def test_missing_parent_is_reported_without_causal_invention(tmp_path):
    s = span()
    s["parent_id"] = "0x" + "f" * 16
    result = assemble_recording(recording(tmp_path, [s]))
    assert any(d.code == "missing_span_reference" for d in result.diagnostics)
    assert not result.executions[0].events[0].causes


def test_missing_commit_retains_observation_and_reports_source(tmp_path, monkeypatch):
    root = recording(tmp_path, [span()])
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["repositories"] = [{"status": "recorded", "path": "ree"}]
    (root / "manifest.json").write_text(json.dumps(manifest))
    ref = SourceReference(artifact_id="repository-0-0", locator=CommitLocator(commit_id="a" * 40))
    record = {
        "context": {"operation_id": "op", "attempt_id": "attempt"},
        "command": {"operation": "build"},
        "run_id": "run",
        "selection_version": 2,
        "capture_status": "captured",
        "operation_status": "succeeded",
        "before_snapshot_id": "b" * 40,
        "after_snapshot_id": "a" * 40,
    }
    monkeypatch.setattr(
        "repo2ree_history.shell.recording.read_operations", lambda *args: iter([(record, ref, root / "ree")])
    )
    monkeypatch.setattr("repo2ree_history.shell.recording.commit_exists", lambda repo, commit: commit == "a" * 40)
    result = assemble_recording(root)
    assert any(e.payload.kind == "git_capture.observed" for e in result.executions[0].events)
    (issue,) = [d for d in result.diagnostics if d.code == "missing_commit"]
    assert issue.source_refs == (ref,)


def test_output_is_deterministic_and_round_trips(tmp_path):
    root = recording(tmp_path, [span()], [state()])
    first = assemble_recording(root)
    assert first == assemble_recording(root)
    output = tmp_path / "out"
    write_outputs(first, output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    write_outputs(assemble_recording(root), output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    assert "Source index" in (output / "evidence-report.md").read_text()


def test_missing_source_reference_is_incomplete(tmp_path):
    result = assemble_recording(recording(tmp_path, [span()]))
    execution = result.executions[0]
    broken = execution.model_copy(update={"artifacts": ()})
    assert "missing_source_artifact" in {i.code for i in validate_execution(broken)}


def test_git_reader_reads_commit_metadata_without_checkout(tmp_path, monkeypatch):
    import os
    import shutil
    import subprocess

    import pytest

    from repo2ree_history.shell.git import commit_exists, read_operations

    executable = os.environ.get("HISTORY_GIT") or shutil.which("git")
    if not executable:
        pytest.skip("Git unavailable")
    monkeypatch.setenv("HISTORY_GIT", executable)
    repository = tmp_path / "ree"
    repository.mkdir()

    def git(*args, content=None):
        return subprocess.run(
            [executable, "-C", str(repository), *args],
            input=content,
            text=True,
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            },
        ).stdout.strip()

    git("init")
    tree = git("mktree", content="")
    record = {"attempt_id": "attempt", "context": {"operation_id": "op", "attempt_id": "attempt"}}
    commit = git(
        "commit-tree",
        tree,
        content="build\n\n" + json.dumps({"schema_version": 2, "kind": "operation.completed", "record": record}),
    )
    git("update-ref", "refs/heads/ree-history", commit)
    rows = list(read_operations(tmp_path, "ree", "repo"))
    assert len(rows) == 1
    assert rows[0][0]["after_snapshot_id"] == commit
    assert isinstance(rows[0][1].locator, CommitLocator)
    assert rows[0][1].locator.commit_id == commit
    assert commit_exists(repository, commit)
    assert not commit_exists(repository, "f" * 40)
    assert not (repository / "ree.json").exists()


def test_repository_path_cannot_escape_recording(tmp_path):
    import pytest

    root = recording(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["repositories"] = [{"status": "recorded", "path": "../outside"}]
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="escapes recording root"):
        assemble_recording(root)
