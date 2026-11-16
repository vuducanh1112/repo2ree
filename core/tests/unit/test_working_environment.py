"""Where a step's scripts ran, as ``ree`` observes it: the host, whether it is a container, the reported image."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.execution import working_environment as we
from repo2ree_core.execution.launch import Launch
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_ree.reserved_paths import RESERVED_LAUNCH_SCRIPT


def test_a_step_records_the_host_and_the_image_its_provider_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(we.REPORTED_IMAGE_VARIABLE, raising=False)
    observed = we.observe_working_environment()
    assert observed.host.arch
    assert observed.reported_image is None

    monkeypatch.setenv(we.REPORTED_IMAGE_VARIABLE, f"python:3.12@sha256:{'a' * 64}")
    assert we.observe_working_environment().reported_image == f"python:3.12@sha256:{'a' * 64}"
    assert we.machine_facts().reported_image == f"python:3.12@sha256:{'a' * 64}"


def test_a_step_knows_it_runs_in_a_container_as_the_engine_marks_one(monkeypatch: pytest.MonkeyPatch) -> None:
    marks = {"/.dockerenv"}
    monkeypatch.setattr(we, "Path", lambda path: type("P", (), {"exists": lambda self: path in marks})())
    assert we.in_container()
    marks.clear()
    assert not we.in_container()


def test_a_probe_reports_what_it_printed_and_none_when_it_ran_out_of_time(tmp_path: Path) -> None:
    done = we.probe(tmp_path, ["sh", "-c", "echo here; echo there >&2; exit 3"], seconds=10)
    assert (done.returncode, done.stdout, done.stderr) == (3, "here\n", "there\n")
    assert we.probe(tmp_path, ["sleep", "5"], seconds=0.2).returncode is None


def test_the_launch_wraps_the_script_and_the_recorder_runs_first(tmp_path: Path) -> None:
    (tmp_path / "ree-scripts").mkdir()
    # Stands in for srun: writes down the command it was handed instead of running it.
    (tmp_path / RESERVED_LAUNCH_SCRIPT).write_text('printf "%s\\n" "$@" > launched.txt\n')
    (tmp_path / "ree-scripts" / "step.sh").write_text("true\n")
    run_workspace_script(
        tmp_path, "ree-scripts/step.sh", log=lambda *_: None, launch=Launch(script=RESERVED_LAUNCH_SCRIPT)
    )
    launched = (tmp_path / "launched.txt").read_text().splitlines()
    assert launched[:2] == ["sh", "-c"]
    assert launched[-2:] == ["sh", "ree-scripts/step.sh"]
