"""Definition patches join their actual filesystem transition to a run."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import get_args

import pytest

from repo2ree_core.domain.ree.transitions import revision_of
from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.tooling import find_tool
from repo2ree_protocol.command import Command, PatchReeDefinitionArgs, PatchReeDefinitionCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult


def git(layout, *args):
    executable = find_tool("git")
    assert executable is not None
    return subprocess.check_output([executable, "--git-dir", str(layout.git_dir), *args]).decode().strip()


@pytest.fixture
def ree(tmp_path, monkeypatch):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="before")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def patch(name="after", *, expected_version="", cancel=None):
    return dispatch.run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": name}, expected_version=expected_version)),
        run_id="patch-run",
        log=lambda *args: None,
        is_canceled=cancel,
    )


def test_patch_captures_files_parent_and_run(ree):
    initial = git(ree, "rev-parse", "HEAD")
    result = patch()
    assert result.status == "succeeded"
    history = result.history.model_dump()
    assert history["before_snapshot_id"] == initial
    after = history["after_snapshot_id"]
    assert git(ree, "rev-parse", f"{after}^") == initial
    assert json.loads(git(ree, "show", f"{after}:ree.json"))["subject"]["definition"]["name"] == "after"
    assert json.loads(git(ree, "show", f"{initial}:ree.json"))["subject"]["definition"]["name"] == "before"
    assert git(ree, "log", "-1", "--format=%s") == "patch_ree_definition"
    assert json.loads(git(ree, "log", "-1", "--format=%b"))["run_id"] == "patch-run"
    assert result.outputs["revision"] == str(revision_of(ReeDirectory(ree).read_ree()))
    metadata = json.loads(git(ree, "log", "-1", "--format=%b"))
    assert metadata["kind"] == "operation.completed"
    assert metadata["schema_version"] == 2
    assert metadata["record"]["context"] == result.context.model_dump(mode="json")
    assert metadata["record"]["result"]["outputs"] == result.outputs
    assert metadata["record"]["result"]["history"] is None
    assert "after_snapshot_id" not in metadata["record"]
    assert "history" not in result.outputs
    assert not list((ree.git_dir / "repo2ree" / "operations").glob("*.json"))


def test_invocation_identity_distinguishes_repeated_run_labels_and_explicit_retries(ree):
    first, second = patch(), patch()
    assert first.context.attempt_id != second.context.attempt_id
    assert first.context.operation_id != second.context.operation_id
    retry = ExecutionContext.new(operation_id=first.context.operation_id)
    result = dispatch.run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "after"})),
        context=retry,
        run_id="patch-run",
        log=lambda *args: None,
    )
    assert result.context == retry
    assert result.history is not None
    assert result.history.changed is False
    records = read_operation_history(ree).operations
    assert [r.sequence for r in records] == [3, 2, 1]
    assert {r.run_id for r in records} == {"patch-run"}
    assert records[0].context is not None
    assert records[-1].context is not None
    assert records[0].context.operation_id == records[-1].context.operation_id


def test_duplicate_attempt_cannot_execute_or_overwrite_its_published_outcome(ree):
    first = patch()
    head = git(ree, "rev-parse", "HEAD")
    repeated = dispatch.run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "duplicate"})),
        context=first.context,
        log=lambda *args: None,
    )
    assert repeated.status == "failed"
    assert repeated.failure is not None
    assert repeated.failure.category == "conflict"
    assert git(ree, "rev-parse", "HEAD") == head
    assert ReeDirectory(ree).read_ree().subject.definition.name == "after"


def test_index_refresh_failure_does_not_reverse_published_success(ree, monkeypatch):
    real_git = GitHistory.git

    def fail_index(self, *args, **kwargs):
        if args[0] == "read-tree" and len(args) == 2 and args[1] != "--empty":
            raise HistoryCaptureError("index unavailable")
        return real_git(self, *args, **kwargs)

    monkeypatch.setattr(GitHistory, "git", fail_index)
    first = patch()
    assert first.status == "succeeded"
    assert first.history.after_snapshot_id == git(ree, "rev-parse", "HEAD")
    record = read_operation_history(ree).operations[0]
    assert record.result is not None
    assert record.result.status == "succeeded"
    assert patch().status == "succeeded"


def test_process_death_after_publication_is_reconciled_from_commit(ree, monkeypatch):
    publish = GitHistory.commit_operation

    def interrupted(self, **kwargs):
        publish(self, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(GitHistory, "commit_operation", interrupted)
    with pytest.raises(KeyboardInterrupt):
        patch()
    pending = next((ree.git_dir / "repo2ree" / "operations").glob("*.json"))
    assert json.loads(pending.read_text())["capture_status"] == "pending"
    record = read_operation_history(ree).operations[0]
    assert record.capture_status == "captured"
    assert record.result is not None
    assert record.result.status == "succeeded"
    assert record.after_snapshot_id == git(ree, "rev-parse", "HEAD")
    # Even unreadable leftovers cannot displace published evidence.
    pending.write_text("incomplete leftover")
    assert read_operation_history(ree).operations[0] == record


def test_noop_and_conflict_each_create_operation_commits(ree):
    original = str(revision_of(ReeDirectory(ree).read_ree()))
    assert patch("before").history.changed is False
    assert git(ree, "rev-list", "--count", "HEAD") == "2"
    assert patch().status == "succeeded"
    result = patch("other", expected_version=original)
    assert result.status == "failed"
    assert result.failure.category == "conflict"
    assert result.history.changed is False
    assert git(ree, "rev-list", "--count", "HEAD") == "4"


def test_preexisting_changes_have_separate_observation(ree):
    ree.overlay_file("external.txt").write_text("unrecorded")
    result = patch()
    before = result.history.before_snapshot_id
    assert git(ree, "show", "-s", "--format=%s", before) == "observe_existing_ree"
    assert git(ree, "diff", "--name-only", before, result.history.after_snapshot_id) == "ree.json"


def test_cancel_before_handler_is_journaled(ree):
    assert patch(cancel=lambda: True).status == "canceled"
    assert git(ree, "rev-list", "--count", "HEAD") == "2"


@pytest.mark.parametrize("after_mutation", [False, True])
def test_capture_failure_reports_whether_handler_ran(ree, monkeypatch, after_mutation):
    method = "commit_operation" if after_mutation else "capture"
    real_capture = getattr(GitHistory, method)

    def failing_capture(self, **kwargs):
        if not after_mutation or kwargs["operation"] == "patch_ree_definition":
            raise HistoryCaptureError("disk full")
        return real_capture(self, **kwargs)

    monkeypatch.setattr(GitHistory, method, failing_capture)
    result = patch()
    assert result.status == "failed"
    assert result.failure.retryable is False
    assert result.history.capture_status == "failed"
    assert result.history.operation_status == ("succeeded" if after_mutation else "not_started")
    assert ReeDirectory(ree).read_ree().subject.definition.name == ("after" if after_mutation else "before")
    assert git(ree, "rev-list", "--count", "HEAD") == "1"
    monkeypatch.setattr(GitHistory, method, real_capture)
    # Retrying observes an already-applied change separately, never attributes it
    # to the retry's no-op patch.
    if after_mutation:
        retry = patch()
        assert retry.history.changed is False
        assert git(ree, "log", "-1", "--format=%s", "HEAD^") == "observe_existing_ree"


@pytest.mark.parametrize("outcome", ["failed", "exception"])
def test_partial_change_captured_with_original_outcome(ree, monkeypatch, outcome):
    def handler(*args, **kwargs):
        ree.overlay_file("partial.txt").write_text("partial")
        if outcome == "exception":
            raise RuntimeError("interrupted handler")
        if outcome == "failed":
            return ActionResult.failed("execution", "partial failure")
        return ActionResult(status="canceled")

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", handler)
    result = patch()
    expected = "failed" if outcome == "exception" else outcome
    assert result.status == expected
    assert result.history.changed is True
    assert git(ree, "show", "HEAD:overlay/partial.txt") == "partial"
    assert json.loads(git(ree, "log", "-1", "--format=%b"))["outcome"] == expected


def test_a_canceled_attempt_is_rolled_back_before_it_is_captured(ree, monkeypatch):
    ree.overlay_file("kept.txt").write_text("before")
    ree.overlay_file("removed.txt").write_text("before")

    def handler(*args, **kwargs):
        ree.overlay_file("kept.txt").write_text("partial")
        ree.overlay_file("removed.txt").unlink()
        ree.overlay_file("created.txt").write_text("partial")
        manifest = json.loads(ree.manifest.read_text())
        manifest["subject"]["definition"]["name"] = "partial"
        ree.manifest.write_text(json.dumps(manifest))
        return ActionResult(status="canceled")

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", handler)
    result = patch()
    assert result.status == "canceled"
    assert result.history.capture_status == "captured"
    assert result.history.changed is False
    assert ree.overlay_file("kept.txt").read_text() == "before"
    assert ree.overlay_file("removed.txt").read_text() == "before"
    assert not ree.overlay_file("created.txt").exists()
    assert ReeDirectory(ree).read_ree().subject.definition.name == "before"
    assert git(ree, "diff", "--name-only", result.history.before_snapshot_id, result.history.after_snapshot_id) == ""
    assert json.loads(git(ree, "log", "-1", "--format=%b"))["outcome"] == "canceled"


def test_concurrent_patches_check_revision_under_capture_lock(ree):
    original = str(revision_of(ReeDirectory(ree).read_ree()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: patch(name, expected_version=original), ["one", "two"]))
    assert sorted(result.status for result in results) == ["failed", "succeeded"]
    assert git(ree, "rev-list", "--count", "HEAD") == "3"


def operation_record(layout, result):
    return next(
        record.model_dump(mode="json")
        for record in read_operation_history(layout).operations
        if record.attempt_id == result.context.attempt_id
    )


def test_noop_cancel_and_failure_each_have_command_record(ree):
    results = [patch("before"), patch(cancel=lambda: True), patch(expected_version="stale")]
    records = [operation_record(ree, result) for result in results]
    assert len({record["attempt_id"] for record in records}) == 3
    assert [record["operation_status"] for record in records] == ["succeeded", "canceled", "failed"]
    for record in records:
        assert record["command"]["operation"] == "patch_ree_definition"
        assert record["before_snapshot_id"] != record["after_snapshot_id"]
        assert record["changed"] is False
        assert record["capture_status"] == "captured"
    assert records[2]["command"]["args"]["expected_version"] == "stale"


def test_executor_bookkeeping_does_not_create_observation(ree):
    from repo2ree_protocol.command import LintScriptsArgs, LintScriptsCommand

    patch()
    ree.run_log("patch-run").write_text('{"type":"result"}\n')
    ree.run_cancel_marker("unrelated").touch()
    ree.upload_staging_file("upload").write_bytes(b"pending")
    (ree.root / "unknown.txt").write_text("outside defined state")
    result = dispatch.run_command(
        LintScriptsCommand(args=LintScriptsArgs(targets=[])), run_id="lint", log=lambda *args: None
    )
    assert result.history is not None
    assert result.history.changed is False
    assert git(ree, "rev-list", "--count", "HEAD") == "3"
    assert "runs/" not in git(ree, "ls-tree", "-r", "--name-only", "HEAD")


def test_write_delete_capture_arbitrary_files_and_command_bytes(ree):
    from repo2ree_protocol.command import DeleteFileArgs, DeleteFileCommand, WriteFileArgs, WriteFileCommand

    content = "arbitrary user .tmp file\n"
    command = WriteFileCommand(args=WriteFileArgs(path="data.tmp", content=content))
    result = dispatch.run_command(command, log=lambda *args: None)
    assert result.status == "succeeded"
    assert operation_record(ree, result)["command"] == command.model_dump(mode="json")
    assert git(ree, "show", "HEAD:overlay/data.tmp") == content.strip()
    result = dispatch.run_command(DeleteFileCommand(args=DeleteFileArgs(path="data.tmp")), log=lambda *args: None)
    assert result.status == "succeeded"
    assert "data.tmp" not in git(ree, "ls-tree", "-r", "--name-only", "HEAD")


def test_process_death_leaves_pending_attempt(ree, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", interrupted)
    with pytest.raises(KeyboardInterrupt):
        patch()
    records = list((ree.git_dir / "repo2ree" / "operations").glob("*.json"))
    record = json.loads(records[0].read_text())
    assert record["capture_status"] == "pending"
    assert record["operation_status"] == "unknown"
    assert record["command"]["args"]["patch"] == {"name": "after"}


# Every member of the public union must pass through capture, including new
# commands. Real handler behavior is covered separately; here each writes one
# state file to prove routing, scope and command serialization together.


@pytest.mark.parametrize("command_cls", get_args(get_args(Command)[0]))
def test_every_command_records_inputs_and_selected_scope(ree, monkeypatch, command_cls):
    values = {
        "review_id": "review-test",
        "experiment_name": "experiment",
        "mode": "upload",
        "upload_token": "upload",
        "archive_name": "source.zip",
        "path": "file.txt",
        "content": "bytes",
        "patch": {},
        "targets": [],
    }
    args_cls = command_cls.model_fields["args"].annotation
    args = args_cls(**{name: values[name] for name, field in args_cls.model_fields.items() if field.is_required()})
    cmd = command_cls(args=args)
    scope = ree.review(args.review_id) if hasattr(args, "review_id") else ree
    author_head = git(ree, "rev-parse", "HEAD")

    def execute(*args, **kwargs):
        scope.overlay.mkdir(parents=True, exist_ok=True)
        scope.overlay_file("operation.txt").write_text(cmd.operation)
        return ActionResult(status="succeeded")

    monkeypatch.setattr(dispatch, "_dispatch", execute)
    result = dispatch.run_command(cmd, log=lambda *args: None)
    assert result.status == "succeeded"
    assert operation_record(ree, result)["command"] == cmd.model_dump(mode="json")
    assert git(scope, "show", "HEAD:overlay/operation.txt") == cmd.operation
    if scope != ree:
        assert git(ree, "rev-parse", "HEAD") == author_head


def test_restoring_a_snapshot_brings_back_lfs_payloads_and_removes_new_recorded_files(ree):
    from repo2ree_core.domain.primitives import ReePath
    from repo2ree_core.domain.ree.model import CapturePolicy
    from repo2ree_core.persistence.history import open_history

    runtime = ree.workspace / "runtime.tar"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(b"runtime built before" * 100)
    directory = ReeDirectory(ree)
    current = directory.read_ree()
    subject = current.subject.model_copy(
        update={"capture": CapturePolicy(lfs_paths=(ReePath("workspace/runtime.tar"),))}
    )
    directory.write_ree(current.model_copy(update={"subject": subject}))
    with open_history(ree) as history:
        snapshot = history.capture(operation="observe_existing_ree")
        assert git(ree, "show", f"{snapshot}:workspace/runtime.tar").startswith("version https://git-lfs")
        runtime.write_bytes(b"half a runtime")
        ree.overlay_file("partial.sh").write_text("partial")
        history.restore(snapshot)
    assert runtime.read_bytes() == b"runtime built before" * 100
    assert not ree.overlay_file("partial.sh").exists()
