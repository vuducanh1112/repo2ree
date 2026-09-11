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
from repo2ree_core.tooling import find_tool
from repo2ree_protocol.command import Command, PatchReeDefinitionArgs, PatchReeDefinitionCommand
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
    history = result.outputs["history"]
    assert history["before_snapshot_id"] == initial
    after = history["after_snapshot_id"]
    assert git(ree, "rev-parse", f"{after}^") == initial
    assert json.loads(git(ree, "show", f"{after}:ree.json"))["subject"]["definition"]["name"] == "after"
    assert json.loads(git(ree, "show", f"{initial}:ree.json"))["subject"]["definition"]["name"] == "before"
    assert git(ree, "log", "-1", "--format=%s") == "patch_ree_definition"
    assert json.loads(git(ree, "log", "-1", "--format=%b"))["run_id"] == "patch-run"
    assert result.outputs["revision"] == str(revision_of(ReeDirectory(ree).read_ree()))


def test_noop_and_conflict_do_not_create_versions(ree):
    original = str(revision_of(ReeDirectory(ree).read_ree()))
    assert patch("before").outputs["history"]["changed"] is False
    assert git(ree, "rev-list", "--count", "HEAD") == "1"
    assert patch().status == "succeeded"
    result = patch("other", expected_version=original)
    assert result.status == "failed"
    assert result.failure.category == "conflict"
    assert result.outputs["history"]["changed"] is False
    assert git(ree, "rev-list", "--count", "HEAD") == "2"


def test_preexisting_changes_have_separate_observation(ree):
    ree.overlay_file("external.txt").write_text("unrecorded")
    result = patch()
    before = result.outputs["history"]["before_snapshot_id"]
    assert git(ree, "show", "-s", "--format=%s", before) == "observe_existing_ree"
    assert git(ree, "diff", "--name-only", before, result.outputs["history"]["after_snapshot_id"]) == "ree.json"


def test_cancel_before_start_does_not_capture(ree):
    assert patch(cancel=lambda: True).status == "canceled"
    assert git(ree, "rev-list", "--count", "HEAD") == "1"


@pytest.mark.parametrize("after_mutation", [False, True])
def test_capture_failure_reports_whether_handler_ran(ree, monkeypatch, after_mutation):
    real_capture = GitHistory.capture

    def failing_capture(self, **kwargs):
        if not after_mutation or kwargs["operation"] == "patch_ree_definition":
            raise HistoryCaptureError("disk full")
        return real_capture(self, **kwargs)

    monkeypatch.setattr(GitHistory, "capture", failing_capture)
    result = patch()
    assert result.status == "failed"
    assert result.failure.retryable is False
    assert result.outputs["history"]["capture_status"] == "failed"
    assert result.outputs["history"]["operation_status"] == ("succeeded" if after_mutation else "not_started")
    assert ReeDirectory(ree).read_ree().subject.definition.name == ("after" if after_mutation else "before")
    assert git(ree, "rev-list", "--count", "HEAD") == "1"
    monkeypatch.setattr(GitHistory, "capture", real_capture)
    # Retrying observes an already-applied change separately, never attributes it
    # to the retry's no-op patch.
    if after_mutation:
        retry = patch()
        assert retry.outputs["history"]["changed"] is False
        assert git(ree, "log", "-1", "--format=%s") == "observe_existing_ree"


@pytest.mark.parametrize("outcome", ["failed", "canceled", "exception"])
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
    assert result.outputs["history"]["changed"] is True
    assert git(ree, "show", "HEAD:overlay/partial.txt") == "partial"
    assert json.loads(git(ree, "log", "-1", "--format=%b"))["outcome"] == expected


def test_concurrent_patches_check_revision_under_capture_lock(ree):
    original = str(revision_of(ReeDirectory(ree).read_ree()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: patch(name, expected_version=original), ["one", "two"]))
    assert sorted(result.status for result in results) == ["failed", "succeeded"]
    assert git(ree, "rev-list", "--count", "HEAD") == "2"


def operation_record(layout, result):
    history = result.outputs["history"]
    root = layout.root / history["scope"]
    return json.loads((root / ".git" / "repo2ree" / "operations" / f"{history['attempt_id']}.json").read_text())


def test_noop_cancel_and_failure_each_have_command_record(ree):
    results = [patch("before"), patch(cancel=lambda: True), patch(expected_version="stale")]
    records = [operation_record(ree, result) for result in results]
    assert len({record["attempt_id"] for record in records}) == 3
    assert [record["operation_status"] for record in records] == ["succeeded", "canceled", "failed"]
    for record in records:
        assert record["command"]["operation"] == "patch_ree_definition"
        assert record["before_snapshot_id"] == record["after_snapshot_id"]
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
    assert result.outputs["history"]["changed"] is False
    assert git(ree, "rev-list", "--count", "HEAD") == "2"
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
