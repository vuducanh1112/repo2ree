"""A command run as a session: its run log, its cancel marker, and the attempts a dead process left behind."""

from __future__ import annotations

import fcntl
import json

import pytest

from repo2ree_core.operations import dispatch
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.session import request_cancel, run_session
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.persistence.run_lock import RUN_LOCK
from repo2ree_protocol.command import PatchReeDefinitionArgs, PatchReeDefinitionCommand


@pytest.fixture
def ree(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="before")
    return layout


def _rename(name: str) -> PatchReeDefinitionCommand:
    return PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": name}))


def _run(ree: ReeLayout, name: str, *, run_id: str = "run-1", lines: list[str] | None = None):
    def emit(_stream: str, _level: str, message: str) -> None:
        if lines is not None:
            lines.append(message)

    return run_session(_rename(name), layout=ree, emit=emit, run_id=run_id)


def test_the_run_log_holds_the_command_its_lines_and_its_result(ree):
    result = _run(ree, "after")

    assert result.status == "succeeded"
    frames = [json.loads(line) for line in ree.run_log("run-1").read_text().splitlines()]
    assert frames[0]["type"] == "command"
    assert frames[0]["command"]["operation"] == "patch_ree_definition"
    assert frames[-1]["type"] == "result"
    assert frames[-1]["result"]["status"] == "succeeded"
    assert {frame["run_id"] for frame in frames} == {"run-1"}


def test_a_requested_cancel_stops_the_run_and_its_marker_goes_with_it(ree):
    request_cancel(ree, "run-1")

    assert _run(ree, "after").status == "canceled"
    assert not ree.run_cancel_marker("run-1").exists()
    assert _run(ree, "after", run_id="run-1").status == "succeeded"


def test_an_attempt_a_dead_process_left_is_settled_before_the_next_command_runs(ree, monkeypatch):
    ree.overlay_file("kept.txt").write_text("before")

    def dies(*args, **kwargs):
        ree.overlay_file("kept.txt").write_text("partial")
        raise KeyboardInterrupt

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", dies)
    with pytest.raises(KeyboardInterrupt):
        _run(ree, "lost", run_id="run-lost")
    monkeypatch.undo()
    [lost] = read_operation_history(ree).operations
    assert lost.capture_status == "pending"

    lines: list[str] = []
    result = _run(ree, "after", run_id="run-2", lines=lines)

    assert result.status == "succeeded"
    assert any(lost.attempt_id in line for line in lines)
    records = {record.attempt_id: record for record in read_operation_history(ree).operations}
    assert records[lost.attempt_id].capture_status == "captured"
    assert records[lost.attempt_id].operation_status == "interrupted"
    assert ree.overlay_file("kept.txt").read_text() == "before"


def test_a_command_is_refused_while_another_runs_in_the_ree_and_settles_nothing(ree, monkeypatch):
    def dies(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(dispatch, "handle_patch_ree_definition", dies)
    with pytest.raises(KeyboardInterrupt):
        _run(ree, "lost", run_id="run-lost")
    monkeypatch.undo()
    with (ree.git_dir / RUN_LOCK).open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        held.write("run-busy")
        held.flush()
        lines: list[str] = []

        result = _run(ree, "after", run_id="run-2", lines=lines)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    assert "run-busy" in result.failure.message
    assert lines == [result.failure.message]
    assert [record.capture_status for record in read_operation_history(ree).operations] == ["pending"]
    assert _run(ree, "after", run_id="run-3").status == "succeeded"
