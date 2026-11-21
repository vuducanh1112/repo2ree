"""Drift: an REE's files changed outside ree are found before the next attempt, refused, and never absorbed."""

import json
import subprocess

import pytest

from repo2ree_core.bundle.download import BundleRefusedError, materialized_ree_download
from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.session import pick_up_authored_edits
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.integrity import find_drift, stamp_rees, stamps_path
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_protocol.command import (
    MaterializeWorkspaceCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    WriteScriptArgs,
    WriteScriptCommand,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.history import DriftedFile
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.reserved_paths import RESERVED_LAUNCH_SCRIPT


def git(layout: ReeLayout, *args: str) -> str:
    executable = find_tool("git")
    assert executable is not None
    return subprocess.check_output([executable, "--git-dir", str(layout.git_dir), *args]).decode().strip()


@pytest.fixture
def ree(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="before")
    return layout


def patch(layout: ReeLayout, name: str = "after"):
    return dispatch.run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": name})),
        run_id="patch-run",
        log=lambda *args: None,
        layout=layout,
    )


def materialized(layout: ReeLayout) -> ReeLayout:
    assert dispatch.run_command(MaterializeWorkspaceCommand(), log=lambda *a: None, layout=layout).status == "succeeded"
    return layout


def test_a_new_ree_has_no_drift(ree):
    assert find_drift(ree) == []
    assert patch(ree).status == "succeeded"
    assert find_drift(ree) == []


def test_a_record_changed_outside_ree_is_refused_and_never_absorbed(ree):
    head = git(ree, "rev-parse", "HEAD")
    manifest = json.loads(ree.manifest.read_text())
    manifest["subject"]["definition"]["name"] = "by hand"
    ree.manifest.write_text(json.dumps(manifest))

    result = patch(ree)

    assert result.status == "failed"
    assert result.failure.category == "precondition"
    assert result.failure.details == {"code": "drift"}
    assert "ree.json" in result.failure.message
    commit = result.history.after_snapshot_id
    assert git(ree, "rev-parse", f"{commit}^") == head
    assert git(ree, "rev-parse", f"{commit}^{{tree}}") == git(ree, "rev-parse", f"{head}^{{tree}}")
    assert "observe_existing_ree" not in git(ree, "log", "--format=%s")
    assert json.loads(ree.manifest.read_text())["subject"]["definition"]["name"] == "by hand"
    [record] = [item for item in read_operation_history(ree).operations if item.run_id == "patch-run"]
    assert record.drift_found == [DriftedFile(path="ree.json", part="records")]


def test_drift_stays_until_it_is_undone(ree):
    script = ree.overlay_file(RESERVED_LAUNCH_SCRIPT)
    original = script.read_bytes()
    ree.overlay_file("notes.txt").write_text("not a script")

    assert patch(ree).status == "failed"
    assert patch(ree).status == "failed"

    ree.overlay_file("notes.txt").unlink()
    assert script.read_bytes() == original
    assert patch(ree).status == "succeeded"


def test_an_edit_in_the_workspace_is_refused_and_kept(ree):
    materialized(ree)
    copy = ree.workspace / RESERVED_LAUNCH_SCRIPT
    copy.write_text(copy.read_text() + "echo edited in the workspace\n")

    result = patch(ree)

    assert result.status == "failed"
    assert f"workspace/{RESERVED_LAUNCH_SCRIPT}" in result.failure.message
    assert copy.read_text().endswith("echo edited in the workspace\n")


def test_a_touched_file_with_the_same_content_is_no_drift(ree):
    materialized(ree)
    copy = ree.workspace / RESERVED_LAUNCH_SCRIPT
    copy.write_bytes(copy.read_bytes())

    assert find_drift(ree) == []


def test_a_script_edited_in_the_overlay_is_recorded_by_an_attempt_that_writes_it(ree):
    materialized(ree)
    script = ree.overlay_file(RESERVED_LAUNCH_SCRIPT)
    edited = script.read_text() + "echo edited in the overlay\n"
    script.write_text(edited)

    invocation = ExecutionContext.new(ree_id="author").model_copy(update={"dispatch_record": "environment-1#7"})
    [recorded] = pick_up_authored_edits(ree, log=lambda *a: None, invocation=invocation)

    assert recorded.status == "succeeded"
    assert recorded.history is not None
    commit = recorded.history.after_snapshot_id
    assert commit is not None
    assert git(ree, "log", "-1", "--format=%s", commit) == "write_script"
    assert git(ree, "show", f"{commit}:overlay/{RESERVED_LAUNCH_SCRIPT}") + "\n" == edited
    assert (ree.workspace / RESERVED_LAUNCH_SCRIPT).read_text() == edited
    [record] = [item for item in read_operation_history(ree).operations if item.run_id.startswith("edit-")]
    assert record.drift_recorded == f"overlay/{RESERVED_LAUNCH_SCRIPT}"
    assert [item.path for item in record.drift_found] == [f"overlay/{RESERVED_LAUNCH_SCRIPT}"]
    assert record.context is not None
    assert (record.context.ree_id, record.context.dispatch_record) == ("author", "environment-1#7")
    assert find_drift(ree) == []
    assert patch(ree).status == "succeeded"


def test_an_overlay_edit_beside_other_drift_is_not_recorded(ree):
    materialized(ree)
    script = ree.overlay_file(RESERVED_LAUNCH_SCRIPT)
    script.write_text(script.read_text() + "echo edited\n")
    (ree.workspace / "stray.txt").write_text("left by something")

    assert pick_up_authored_edits(ree, log=lambda *a: None) == []
    assert patch(ree).status == "failed"
    assert script.read_text().endswith("echo edited\n")


def test_an_attempt_rolled_back_leaves_the_workspace_scripts_as_the_ree_records_them(ree, monkeypatch):
    materialized(ree)
    copy = ree.workspace / RESERVED_LAUNCH_SCRIPT
    before = copy.read_text()

    def dies(*args, **kwargs):
        raise HistoryCaptureError("locked")

    monkeypatch.setattr(GitHistory, "commit_operation", dies)
    written = dispatch.run_command(
        WriteScriptCommand(args=WriteScriptArgs(path=RESERVED_LAUNCH_SCRIPT, content="echo never recorded\n")),
        log=lambda *a: None,
        layout=ree,
    )
    monkeypatch.undo()

    assert written.status == "failed"
    assert copy.read_text() == before
    assert find_drift(ree) == []


def test_laying_the_workspace_out_again_discards_its_drift_and_names_it(ree):
    materialized(ree)
    copy = ree.workspace / RESERVED_LAUNCH_SCRIPT
    before = copy.read_text()
    copy.write_text("echo edited in the workspace\n")
    (ree.workspace / "stray.txt").write_text("left by something")

    assert patch(ree).status == "failed"
    laid_out = dispatch.run_command(MaterializeWorkspaceCommand(), log=lambda *a: None, layout=ree, run_id="lay-out")

    assert laid_out.status == "succeeded"
    assert copy.read_text() == before
    assert find_drift(ree) == []
    [record] = [item for item in read_operation_history(ree).operations if item.run_id == "lay-out"]
    assert [item.path for item in record.drift_found] == ["workspace/ree-scripts/launch.sh", "workspace/stray.txt"]
    assert patch(ree).status == "succeeded"


def test_laying_the_workspace_out_again_is_refused_for_drift_elsewhere(ree):
    materialized(ree)
    ree.overlay_file("notes.txt").write_text("not a script")

    assert dispatch.run_command(MaterializeWorkspaceCommand(), log=lambda *a: None, layout=ree).status == "failed"


def test_a_history_reset_outside_ree_is_refused_and_kept_beside_it_until_put_back(ree):
    first = git(ree, "rev-parse", "refs/heads/ree-history")
    assert patch(ree, "second").status == "succeeded"
    left = git(ree, "rev-parse", "refs/heads/ree-history")
    git(ree, "update-ref", "refs/heads/ree-history", first)

    refused = patch(ree, "third")
    again = patch(ree, "third")

    assert refused.status == again.status == "failed"
    assert refused.failure is not None
    assert f"git update-ref refs/heads/ree-history {left}" in refused.failure.message
    assert refused.history is not None
    assert (refused.history.capture_status, refused.history.after_snapshot_id) == ("failed", None)
    assert refused.history.record_digest is not None
    assert git(ree, "rev-parse", "refs/heads/ree-history") == first
    git(ree, "update-ref", "refs/heads/ree-history", left)
    assert patch(ree, "third").status == "succeeded"


def test_a_commit_made_outside_ree_is_drift_even_when_the_files_are_as_they_were(ree):
    head = git(ree, "rev-parse", "refs/heads/ree-history")
    identity = ("-c", "user.name=someone", "-c", "user.email=someone@example.invalid")
    by_hand = git(ree, *identity, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "by hand")
    git(ree, "update-ref", "refs/heads/ree-history", by_hand)

    assert find_drift(ree) == [DriftedFile(path=".git/refs/heads/ree-history", part="history")]
    assert patch(ree).status == "failed"


def test_a_file_changed_in_a_review_is_drift_of_the_ree(ree):
    review = ree.review("review-1")
    review.root.mkdir(parents=True)
    initialize_ree(review, name="review")
    stamp_rees(ree, review)
    review.overlay_file(RESERVED_LAUNCH_SCRIPT).write_text("echo changed in the review\n")

    assert find_drift(ree) == [DriftedFile(path=f"reviews/review-1/overlay/{RESERVED_LAUNCH_SCRIPT}", part="overlay")]
    assert patch(ree).status == "failed"


def committed_by_hand(layout: ReeLayout) -> str:
    """A commit on the REE's history made with git, as a person would, of the REE's files as they are."""
    head = git(layout, "rev-parse", "refs/heads/ree-history")
    identity = ("-c", "user.name=someone", "-c", "user.email=someone@example.invalid")
    by_hand = git(layout, *identity, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "my fix")
    git(layout, "update-ref", "refs/heads/ree-history", by_hand)
    return head


def test_a_bundle_of_a_history_committed_to_with_git_is_refused_until_it_is_put_back(ree):
    assert patch(ree).status == "succeeded"
    left = committed_by_hand(ree)

    hint = f"git update-ref refs/heads/ree-history {left}"
    with pytest.raises(BundleRefusedError, match=hint), materialized_ree_download(ree):
        pass

    git(ree, "update-ref", "refs/heads/ree-history", left)
    with materialized_ree_download(ree) as archive:
        assert archive.is_file()


def test_a_bundle_of_a_file_changed_outside_ree_is_refused(ree):
    ree.manifest.write_text(ree.manifest.read_text() + " ")

    with pytest.raises(BundleRefusedError, match=r"ree\.json"), materialized_ree_download(ree):
        pass


def test_a_bundle_of_a_history_no_attempt_ended_is_refused_without_stamps(ree):
    committed_by_hand(ree)
    stamps_path(ree).unlink()

    with pytest.raises(BundleRefusedError, match="a commit no ree command made"), materialized_ree_download(ree):
        pass


def test_an_ree_no_command_worked_on_has_nothing_to_bundle(ree):
    with pytest.raises(BundleRefusedError, match="nothing to bundle yet"), materialized_ree_download(ree):
        pass
