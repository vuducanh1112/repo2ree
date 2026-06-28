"""Tests for the runnable runner (experiment/run.py).

Each runnable owns a run script that fully defines how it executes; the runner
runs it from the workspace root, captures stdout/stderr, and evaluates declared
outputs against the workspace on the host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from repo2ree_core.experiment.experiment import (
    ContainsMatch,
    CustomMatch,
    ExpectedOutput,
    Experiment,
    FileSource,
    StdoutSource,
)
from repo2ree_core.experiment.run import run_runnable

# ================================================
# Helpers
# ================================================


def _log() -> tuple[list[tuple[str, str, str]], Any]:
    msgs: list[tuple[str, str, str]] = []
    return msgs, lambda stream, level, msg: msgs.append((stream, level, msg))


def _experiment(
    body: str = "echo hello",
    *,
    workspace: Path,
    outputs: list[ExpectedOutput] | None = None,
    script_rel: str = "ree/experiments/test-exp.sh",
) -> Experiment:
    script = workspace / script_rel
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(body)
    return Experiment(
        name="test-exp",
        description="",
        run_script=script_rel,
        runtime_estimate="",
        outputs=outputs or [],
    )


def _run(
    workspace: Path,
    runnable: Experiment,
    *,
    mode: Literal["verify", "snapshot"] = "verify",
    run_id: str = "r1",
):
    msgs, log = _log()
    outcome = run_runnable(
        workspace=workspace,
        runnable=runnable,
        label="test",
        mode=mode,
        run_id=run_id,
        log=log,
        is_canceled=lambda: False,
    )
    return outcome, msgs


# ================================================
# Basic execution
# ================================================


def test_script_runs_and_succeeds(tmp_path):
    out_file = tmp_path / "out.txt"
    exp = _experiment(body=f"echo experiment_ran > {out_file}", workspace=tmp_path)
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert out_file.read_text().strip() == "experiment_ran"


def test_missing_script_fails(tmp_path):
    exp = Experiment(name="x", run_script="ree/experiments/nope.sh")
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"


def test_script_runs_from_workspace_root(tmp_path, monkeypatch):
    monkeypatch.chdir("/")
    exp = _experiment(body="pwd > cwd.txt", workspace=tmp_path)
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert (tmp_path / "cwd.txt").read_text().strip() == str(tmp_path.resolve())


def test_nonzero_exit_fails(tmp_path):
    exp = _experiment(body="exit 2", workspace=tmp_path)
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.get("exitCode") == 2


# ================================================
# Output evaluation (host-side)
# ================================================


def test_stdout_output_verify_passes(tmp_path):
    exp = _experiment(
        body="echo hello",
        workspace=tmp_path,
        outputs=[
            ExpectedOutput(source=StdoutSource(kind="stdout"), match=ContainsMatch(mode="contains", value="hello"))
        ],
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.get("verdict") == "pass"


def test_stdout_output_verify_fails_on_mismatch(tmp_path):
    exp = _experiment(
        body="echo hello",
        workspace=tmp_path,
        outputs=[
            ExpectedOutput(source=StdoutSource(kind="stdout"), match=ContainsMatch(mode="contains", value="NOTHERE"))
        ],
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.get("verdict") == "fail"


def test_file_output_read_from_workspace(tmp_path):
    exp = _experiment(
        body="mkdir -p results && echo expected > results/out.txt",
        workspace=tmp_path,
        outputs=[
            ExpectedOutput(
                source=FileSource(kind="file", path="results/out.txt"),
                match=ContainsMatch(mode="contains", value="expected"),
            )
        ],
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.get("verdict") == "pass"


def test_file_output_missing_fails(tmp_path):
    exp = _experiment(
        body="true",
        workspace=tmp_path,
        outputs=[
            ExpectedOutput(
                source=FileSource(kind="file", path="results/out.txt"),
                match=ContainsMatch(mode="contains", value="expected"),
            )
        ],
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.get("verdict") == "fail"


def test_custom_match_runs_on_host(tmp_path):
    exp = _experiment(
        body="echo 42",
        workspace=tmp_path,
        outputs=[
            ExpectedOutput(
                source=StdoutSource(kind="stdout"),
                match=CustomMatch(mode="custom", value="grep -q 42"),
            )
        ],
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.get("verdict") == "pass"


# ================================================
# Snapshot mode
# ================================================


def test_snapshot_mode_records_stdout_baseline(tmp_path):
    exp = _experiment(
        body="echo baseline-text",
        workspace=tmp_path,
        outputs=[ExpectedOutput(source=StdoutSource(kind="stdout"), match=ContainsMatch(mode="contains", value=""))],
    )
    outcome, _ = _run(tmp_path, exp, mode="snapshot", run_id="snap1")
    assert outcome.status == "succeeded"
    assert outcome.snapshot_to_persist is not None
    assert len(outcome.snapshot_to_persist) == 1


def test_snapshot_skipped_when_command_fails(tmp_path):
    exp = _experiment(body="exit 1", workspace=tmp_path)
    outcome, _ = _run(tmp_path, exp, mode="snapshot", run_id="snap2")
    assert outcome.run_outputs.get("snapshotApplied") is False
    assert outcome.snapshot_to_persist is None
