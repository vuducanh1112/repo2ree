"""Tests for the runnable runner (experiment/run.py).

Each runnable owns a run script that fully defines how it executes; the runner
runs it from the workspace root and captures stdout/stderr. When the runnable
declares a verify script, the runner executes it afterwards — a plain script run
from the workspace root with nothing injected into its environment, exactly like
the run script — and its exit code is the verdict. A verify script that wants to
check the run's stdout reads it from a workspace file the run script wrote.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.execution.experiment.run import run_runnable

# ================================================
# Helpers
# ================================================


def _log() -> tuple[list[tuple[str, str, str]], Any]:
    msgs: list[tuple[str, str, str]] = []
    return msgs, lambda stream, level, msg: msgs.append((stream, level, msg))


def _write_script(workspace: Path, rel: str, body: str) -> str:
    script = workspace / rel
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(body)
    return rel


def _experiment(
    body: str = "echo hello",
    *,
    workspace: Path,
    verify_body: str | None = None,
    script_rel: str = "ree-scripts/experiments/test-exp.sh",
    verify_rel: str = "ree-scripts/experiments/test-exp.verify.sh",
) -> Experiment:
    _write_script(workspace, script_rel, body)
    verify_script = ""
    if verify_body is not None:
        verify_script = _write_script(workspace, verify_rel, verify_body)
    return Experiment(
        name="test-exp",
        description="",
        run_script=script_rel,
        verify_script=verify_script,
        runtime_estimate="",
    )


def _run(workspace: Path, runnable: Experiment, *, run_id: str = "r1"):
    msgs, log = _log()
    outcome = run_runnable(
        workspace=workspace,
        runnable=runnable,
        label="test",
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
    assert outcome.run_outputs.verdict == "pass"
    assert out_file.read_text().strip() == "experiment_ran"


def test_missing_script_fails(tmp_path):
    exp = Experiment(name="x", run_script="ree-scripts/experiments/nope.sh")
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
    assert outcome.run_outputs.exit_code == 2
    assert outcome.run_outputs.verdict == "fail"


# ================================================
# Verify script
# ================================================


def test_verify_script_runs_from_workspace_root(tmp_path, monkeypatch):
    monkeypatch.chdir("/")
    exp = _experiment(
        body="echo hello",
        workspace=tmp_path,
        verify_body="pwd > verify-cwd.txt",
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.verdict == "pass"
    assert outcome.run_outputs.verify_exit_code == 0
    assert (tmp_path / "verify-cwd.txt").read_text().strip() == str(tmp_path.resolve())


def test_verify_script_reads_materialized_stdout(tmp_path):
    # The run script materializes its stdout to a workspace file; the verify
    # script reads it back — there is no injected variable for the streams.
    exp = _experiment(
        body="echo the-claimed-result | tee run.log",
        workspace=tmp_path,
        verify_body="grep -q the-claimed-result run.log",
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.verdict == "pass"
    assert outcome.run_outputs.verify_exit_code == 0


def test_verify_script_failure_fails_the_run(tmp_path):
    exp = _experiment(
        body="echo hello | tee run.log",
        workspace=tmp_path,
        verify_body="grep -q NOTHERE run.log",
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.verdict == "fail"
    assert outcome.run_outputs.verify_exit_code == 1


def test_verify_script_reads_file_outputs_from_workspace(tmp_path):
    exp = _experiment(
        body="mkdir -p results && echo expected > results/out.txt",
        workspace=tmp_path,
        verify_body="grep -q expected results/out.txt",
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "succeeded"
    assert outcome.run_outputs.verdict == "pass"


def test_no_injected_environment_for_verify_script(tmp_path):
    # The old contract exported R2R_* variables; nothing is injected now, so a
    # verify script that relies on them sees empty values and fails.
    exp = _experiment(
        body="echo hello",
        workspace=tmp_path,
        verify_body='[ -n "${R2R_RUN_STDOUT:-}" ]',
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.verdict == "fail"


def test_missing_verify_script_fails(tmp_path):
    exp = _experiment(body="echo hello", workspace=tmp_path)
    exp = exp.model_copy(update={"verify_script": "ree-scripts/experiments/nope.verify.sh"})
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.verdict == "fail"


def test_verify_runs_even_when_run_fails(tmp_path):
    marker = tmp_path / "verify-ran.txt"
    exp = _experiment(
        body="exit 3",
        workspace=tmp_path,
        verify_body=f"touch {marker}",
    )
    outcome, _ = _run(tmp_path, exp)
    assert outcome.status == "failed"
    assert outcome.run_outputs.verdict == "fail"
    # The verify script still runs (it may want to report on a failed run), but
    # a failed run can never verify to pass.
    assert outcome.run_outputs.verify_exit_code == 0
    assert marker.exists()
