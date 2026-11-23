import json
import subprocess

import pytest
from recorded_ree import as_recorded

from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.session import run_session
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_protocol.command import PatchReeDefinitionArgs, PatchReeDefinitionCommand
from repo2ree_protocol.result import ActionResult, DriftedFile
from repo2ree_protocol.tools import find_tool


def git(layout, *args):
    executable = find_tool("git")
    assert executable is not None
    return subprocess.check_output([executable, "--git-dir", str(layout.git_dir), *args]).decode().strip()


@pytest.fixture
def ree(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="before")
    layout.overlay_file("kept.txt").write_text("before")
    return as_recorded(layout)


def patch(layout: ReeLayout, name="after"):
    return dispatch.run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": name})),
        run_id="patch-run",
        log=lambda *args: None,
        layout=layout,
    )


def handled_by(monkeypatch, handler):
    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", handler)
    monkeypatch.setattr(dispatch, "validate_outputs", lambda *_args: None)


def test_an_edit_beside_a_running_attempt_is_neither_seen_nor_committed_and_is_found_after_it(ree, monkeypatch):
    seen = []

    def handler(*_args, layout, **_kwargs):
        ree.overlay_file("kept.txt").write_text("edited beside the attempt")
        seen.append(layout.overlay_file("kept.txt").read_text())
        layout.overlay_file("written.txt").write_text("by the attempt")
        return ActionResult(status="succeeded")

    handled_by(monkeypatch, handler)
    result = patch(ree)

    assert result.status == "succeeded", result.failure
    assert seen == ["before"]
    after = result.history.after_snapshot_id
    assert git(ree, "show", f"{after}:overlay/kept.txt") == "before"
    assert git(ree, "show", f"{after}:overlay/written.txt") == "by the attempt"
    assert ree.overlay_file("kept.txt").read_text() == "edited beside the attempt"
    assert ree.overlay_file("written.txt").read_text() == "by the attempt"
    assert result.history.drift_after == [DriftedFile(path="overlay/kept.txt", part="overlay")]
    [record] = [item for item in read_operation_history(ree).operations if item.run_id == "patch-run"]
    assert record.drift_after == [DriftedFile(path="overlay/kept.txt", part="overlay")]
    assert not (ree.root / ".stage").exists()

    monkeypatch.undo()
    refused = patch(ree, "again")
    assert refused.failure is not None
    assert refused.failure.details == {"code": "drift"}


def test_a_file_the_attempt_changed_and_was_edited_beside_it_keeps_the_edit(ree, monkeypatch):
    def handler(*_args, layout, **_kwargs):
        ree.overlay_file("kept.txt").write_text("edited beside the attempt")
        layout.overlay_file("kept.txt").write_text("by the attempt")
        return ActionResult(status="succeeded")

    handled_by(monkeypatch, handler)
    result = patch(ree)

    assert git(ree, "show", f"{result.history.after_snapshot_id}:overlay/kept.txt") == "by the attempt"
    assert ree.overlay_file("kept.txt").read_text() == "edited beside the attempt"
    assert result.history.drift_after == [DriftedFile(path="overlay/kept.txt", part="overlay")]


def test_an_edit_beside_an_attempt_whose_executor_was_lost_is_named_when_it_is_settled(ree, monkeypatch):
    def dies(*_args, layout, **_kwargs):
        ree.overlay_file("kept.txt").write_text("edited beside the attempt")
        layout.overlay_file("kept.txt").write_text("partial")
        raise KeyboardInterrupt

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", dies)
    with pytest.raises(KeyboardInterrupt):
        run_session(
            PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "lost"})),
            layout=ree,
            emit=lambda *args: None,
            run_id="run-lost",
        )
    monkeypatch.undo()
    [lost] = read_operation_history(ree).operations[-1:]

    run_session(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "after"})),
        layout=ree,
        emit=lambda *args: None,
        run_id="run-next",
    )

    settled = next(item for item in read_operation_history(ree).operations if item.attempt_id == lost.attempt_id)
    assert settled.operation_status == "interrupted"
    assert settled.drift_after == [DriftedFile(path="overlay/kept.txt", part="overlay")]


def test_an_attempt_left_clean_finds_nothing_after_it(ree):
    result = patch(ree)

    assert result.status == "succeeded"
    assert result.history.drift_after == []
    assert ReeDirectory(ree).read_ree().subject.definition.name == "after"


def test_what_no_history_holds_reaches_the_ree_as_the_attempt_left_it(ree, monkeypatch):
    ree.upstream.mkdir(parents=True, exist_ok=True)
    (ree.upstream / "gone.txt").write_text("removed by the attempt")
    (ree.upstream / "replaced.txt").write_text("before")

    def handler(*_args, layout, **_kwargs):
        (layout.upstream / "gone.txt").unlink()
        (layout.upstream / "replaced.txt").write_text("replaced")
        (layout.upstream / "nested").mkdir()
        (layout.upstream / "nested" / "new.txt").write_text("new")
        return ActionResult(status="succeeded")

    handled_by(monkeypatch, handler)
    result = patch(ree)

    assert result.status == "succeeded"
    assert not (ree.upstream / "gone.txt").exists()
    assert (ree.upstream / "replaced.txt").read_text() == "replaced"
    assert (ree.upstream / "nested" / "new.txt").read_text() == "new"


def test_a_canceled_attempt_leaves_nothing_of_what_it_did(ree, monkeypatch):
    def handler(*_args, layout, **_kwargs):
        layout.overlay_file("kept.txt").write_text("partial")
        layout.upstream.mkdir(parents=True, exist_ok=True)
        (layout.upstream / "partial.txt").write_text("partial")
        return ActionResult(status="canceled")

    handled_by(monkeypatch, handler)
    result = patch(ree)

    assert result.status == "canceled", result.failure
    assert result.history.changed is False
    assert ree.overlay_file("kept.txt").read_text() == "before"
    assert not (ree.upstream / "partial.txt").exists()


def test_an_attempt_that_changes_a_history_it_is_not_recorded_in_fails_its_capture(ree, monkeypatch):
    review = ree.review("review-one")
    review.root.mkdir(parents=True)
    review.metadata.write_text(json.dumps({"review": "as recorded"}))
    as_recorded(review)

    def handler(*_args, layout, **_kwargs):
        layout.review("review-one").metadata.write_text(json.dumps({"review": "changed by an author step"}))
        return ActionResult(status="succeeded")

    handled_by(monkeypatch, handler)
    result = patch(ree)

    assert result.history.capture_status == "failed"
    assert "changed what it is not recorded in: reviews/review-one" in result.failure.message
    assert json.loads(review.metadata.read_text()) == {"review": "as recorded"}
    assert ReeDirectory(ree).read_ree().subject.definition.name == "before"
