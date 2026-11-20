"""Drift: an REE's files changed outside ree are found before the next attempt, refused, and never absorbed."""

import json
import subprocess

import pytest

from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.session import pick_up_authored_edits
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.integrity import find_drift
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
