"""Drift: an REE's files changed outside ree are found before the next attempt, refused, and never absorbed."""

import json
import subprocess
import zipfile

import pytest

from repo2ree_core.bundle.download import BundleRefusedError, materialized_ree_download
from repo2ree_core.bundle.repository_restore import restore_repository
from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.session import pick_up_authored_edits
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError, open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.workspace.integrity import find_drift
from repo2ree_protocol.command import (
    MaterializeWorkspaceArgs,
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
    # Nothing is committed for the refusal: it is kept beside the history, which stays where ree left it.
    assert (result.history.after_snapshot_id, result.history.capture_status) == (None, "failed")
    assert result.history.record_digest is not None
    assert git(ree, "rev-parse", "HEAD") == head
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
    ree.manifest.write_text(ree.manifest.read_text() + " ")

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
    stray = ree.workspace / "stray.txt"
    stray.write_text("left by something")

    assert patch(ree).status == "failed"
    laid_out = dispatch.run_command(MaterializeWorkspaceCommand(), log=lambda *a: None, layout=ree, run_id="lay-out")

    assert laid_out.status == "succeeded"
    assert copy.read_text() == before
    assert find_drift(ree) == []
    [record] = [item for item in read_operation_history(ree).operations if item.run_id == "lay-out"]
    # A file nothing lays out is recorded nowhere, so it never drifted, and laying out again leaves it.
    assert [item.path for item in record.drift_found] == ["workspace/ree-scripts/launch.sh"]
    assert stray.read_text() == "left by something"
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


def test_a_bundle_of_a_history_committed_to_with_git_is_refused_without_its_reflog(ree):
    assert patch(ree).status == "succeeded"
    left = committed_by_hand(ree)
    git(ree, "reflog", "expire", "--expire=now", "--all")

    hint = f"update-ref refs/heads/ree-history {left}"
    with pytest.raises(BundleRefusedError, match=hint), materialized_ree_download(ree):
        pass


def test_an_ree_no_command_worked_on_has_nothing_to_bundle(ree):
    with pytest.raises(BundleRefusedError, match="nothing to bundle yet"), materialized_ree_download(ree):
        pass


def test_ree_s_commits_name_their_parent_and_tree_and_its_moves_are_marked(ree):
    assert patch(ree).status == "succeeded"
    head = git(ree, "rev-parse", "refs/heads/ree-history")
    metadata = json.loads(git(ree, "log", "-1", "--format=%b", head))

    assert metadata["parent"] == git(ree, "rev-parse", f"{head}^")
    assert metadata["tree"] == git(ree, "rev-parse", f"{head}^{{tree}}")
    assert git(ree, "reflog", "show", "--format=%gs", "refs/heads/ree-history").splitlines()[0].startswith("repo2ree ")
    assert git(ree, "config", "gc.reflogExpire") == "never"


def test_a_record_edited_is_found_by_git(ree):
    tamper = json.loads(ree.manifest.read_text())
    tamper["subject"]["definition"]["name"] = "by hand"
    ree.manifest.write_text(json.dumps(tamper))

    result = patch(ree)

    assert result.status == "failed"
    assert result.failure.details == {"code": "drift"}
    assert "observe_existing_ree" not in git(ree, "log", "--format=%s")


def test_a_history_reset_is_found_by_the_reflog(ree):
    first = git(ree, "rev-parse", "refs/heads/ree-history")
    assert patch(ree, "second").status == "succeeded"
    left = git(ree, "rev-parse", "refs/heads/ree-history")
    git(ree, "update-ref", "refs/heads/ree-history", first)

    # The ref went back; the files stay as the later attempt left them, so they differ from it too.
    assert DriftedFile(path=".git/refs/heads/ree-history", part="history") in find_drift(ree)
    refused = patch(ree, "third")
    assert refused.failure is not None
    assert f"git update-ref refs/heads/ree-history {left}" in refused.failure.message


def test_a_history_reset_to_a_commit_of_ree_s_while_the_reflog_is_lost_is_found_only_by_its_files(ree):
    # Every commit is still ree's, and nothing says where ree left the history: only the files, which stay as the
    # later attempt left them, are found. The refusal is kept beside the history, so nothing moves its ref.
    first = git(ree, "rev-parse", "refs/heads/ree-history")
    assert patch(ree, "second").status == "succeeded"
    git(ree, "reflog", "expire", "--expire=now", "--all")
    git(ree, "update-ref", "refs/heads/ree-history", first)

    assert find_drift(ree) == [DriftedFile(path="ree.json", part="records")]
    assert patch(ree, "third").status == "failed"
    assert git(ree, "rev-parse", "refs/heads/ree-history") == first


def test_a_commit_amended_with_git_names_another_tree_than_its_own(ree):
    assert patch(ree).status == "succeeded"
    ree.manifest.write_text(ree.manifest.read_text() + " ")
    head = git(ree, "rev-parse", "refs/heads/ree-history")
    message = git(ree, "log", "-1", "--format=%B", head)
    git(ree, "--work-tree", str(ree.root), "add", "ree.json")
    tree = git(ree, "--work-tree", str(ree.root), "write-tree")
    identity = ("-c", "user.name=someone", "-c", "user.email=someone@example.invalid")
    amended = git(ree, *identity, "commit-tree", tree, "-p", f"{head}^", "-m", message)
    git(ree, "update-ref", "refs/heads/ree-history", amended)
    git(ree, "reflog", "expire", "--expire=now", "--all")

    with open_history(ree) as history:
        assert history.unrecorded(amended) == "it names another tree than its own, as a commit amended by git does"
    assert DriftedFile(path=".git/refs/heads/ree-history", part="history") in find_drift(ree)


def test_a_commit_copied_onto_another_parent_names_another_parent_than_its_own(ree):
    assert patch(ree, "second").status == "succeeded"
    head = git(ree, "rev-parse", "refs/heads/ree-history")
    message = git(ree, "log", "-1", "--format=%B", head)
    identity = ("-c", "user.name=someone", "-c", "user.email=someone@example.invalid")
    # Copied onto the commit it followed, as a cherry-pick onto the history's head copies it.
    copied = git(ree, *identity, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", message)

    with open_history(ree) as history:
        assert history.unrecorded(head) is None
        assert history.unrecorded(copied) == "it names another parent than its own, as a commit copied by git does"


def test_a_bundle_whose_history_holds_a_commit_ree_did_not_make_is_not_loaded(ree, tmp_path):
    assert patch(ree).status == "succeeded"
    with materialized_ree_download(ree) as archive, zipfile.ZipFile(archive) as zipped:
        zipped.extractall(tmp_path / "export")
    exported = ReeLayout(root=tmp_path / "export" / "ree")
    head = git(exported, "rev-parse", "refs/heads/ree-history")
    identity = ("-c", "user.name=someone", "-c", "user.email=someone@example.invalid")
    by_hand = git(exported, *identity, "commit-tree", f"{head}^{{tree}}", "-p", head, "-m", "my fix")
    git(exported, "update-ref", "refs/heads/ree-history", by_hand)
    metadata = json.loads((tmp_path / "export" / "export.json").read_text())
    metadata["scopes"][0]["head"] = by_hand
    (tmp_path / "export" / "export.json").write_text(json.dumps(metadata))
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")

    with pytest.raises(ValueError, match=f"holds {by_hand}, which ree did not make"):
        restore_repository(destination, tmp_path / "export")


def declared(layout: ReeLayout) -> ReeLayout:
    """The REE with a source file to lay out and an experiment environment declared at ``venv``."""
    (layout.upstream / "src").mkdir(parents=True, exist_ok=True)
    (layout.upstream / "src" / "config.h").write_text("#define X 1\n")
    materialized(layout)
    patched = dispatch.run_command(
        PatchReeDefinitionCommand(
            args=PatchReeDefinitionArgs(patch={"experiment_environment": {"artifact_path": "venv"}})
        ),
        log=lambda *args: None,
        layout=layout,
    )
    assert patched.status == "succeeded", patched
    return layout


def test_a_source_file_a_step_rewrites_is_recorded_and_is_no_drift(ree, monkeypatch):
    declared(ree)

    real = getattr(dispatch, "handle_patch_ree_definition")  # noqa: B009 — not exported, replaced below

    def configures(*args, **kwargs):
        (ree.workspace / "src" / "config.h").write_text("#define X 2\n")
        return real(*args, **kwargs)

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", configures)
    configured = patch(ree, "configured")
    monkeypatch.undo()
    assert configured.history is not None

    [record] = [
        item for item in read_operation_history(ree).operations if item.attempt_id == configured.history.attempt_id
    ]
    assert list(record.workspace_changed or {}) == ["src/config.h"]
    assert find_drift(ree) == []
    (ree.workspace / "src" / "config.h").write_text("#define X 3\n")
    assert find_drift(ree) == [DriftedFile(path="workspace/src/config.h", part="workspace")]


def test_what_nothing_lays_out_is_no_drift(ree):
    declared(ree)
    (ree.workspace / "venv").mkdir()
    (ree.workspace / "venv" / "python").write_text("built")
    (ree.workspace / "__pycache__").mkdir()
    (ree.workspace / "__pycache__" / "x.pyc").write_bytes(b"cache")

    assert find_drift(ree) == []
    (ree.workspace / "venv" / "python").write_text("edited by hand")
    # The experiment environment is vouched for by the receipts that digest it, not by a drift check.
    assert find_drift(ree) == []


def test_a_derived_file_is_compared_with_its_input_when_the_marker_is_lost(ree):
    declared(ree)
    marker = DriftedFile(path=ree.materialize_marker.name, part="records")
    ree.materialize_marker.unlink()
    # The marker is a record of the REE, so losing it is drift too; without it, files are read to compare.
    assert find_drift(ree) == [marker]

    (ree.workspace / "src" / "config.h").write_text("#define X 9\n")
    assert find_drift(ree) == [marker, DriftedFile(path="workspace/src/config.h", part="workspace")]


def test_a_derived_file_whose_mode_changed_is_drift_though_its_time_did_not(ree):
    declared(ree)
    target = ree.workspace / "src" / "config.h"
    target.chmod(0o755)

    assert find_drift(ree) == [DriftedFile(path="workspace/src/config.h", part="workspace")]


def test_laying_out_again_keeps_the_experiment_environment_and_clean_does_not(ree):
    declared(ree)
    environment = ree.workspace / "venv" / "python"
    environment.parent.mkdir()
    environment.write_text("built")
    (ree.workspace / "src" / "config.h").write_text("edited")

    materialized(ree)
    assert environment.is_file()
    assert (ree.workspace / "src" / "config.h").read_text() == "#define X 1\n"
    cleaned = dispatch.run_command(
        MaterializeWorkspaceCommand(args=MaterializeWorkspaceArgs(clean=True)), log=lambda *a: None, layout=ree
    )
    assert cleaned.status == "succeeded"
    assert not environment.exists()
