"""Every script runs through the REE's launch script when it declares one, and the step learns where it ran."""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.execution.launch import RECORD_PREFIX, Launch, declared_launch
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_protocol.frames import LogSink
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import LaunchDefinition
from repo2ree_ree.primitives import LaunchOption
from repo2ree_ree.reserved_paths import RESERVED_LAUNCH_SCRIPT

# Stands in for srun: puts the command in a "job step", records the options it was given, and runs it.
FAKE_SRUN = """#!/usr/bin/env sh
set -eu
SLURM_JOB_ID=4711
SLURM_STEP_ID=0
export SLURM_JOB_ID SLURM_STEP_ID
printf '%s\\n' "${REE_LAUNCH_OPTIONS:-}" > launch-options.txt
exec "$@"
"""


def _quiet() -> LogSink:
    return lambda *_args: None


def _workspace(root: Path) -> Path:
    scripts = root / "ree-scripts"
    scripts.mkdir(parents=True)
    (root / RESERVED_LAUNCH_SCRIPT).write_text(FAKE_SRUN)
    (scripts / "step.sh").write_text("printf '%s\\n' \"${SLURM_JOB_ID:-none}\" > ran-in.txt\n")
    return root


def test_a_launched_script_runs_inside_the_launch_and_the_step_learns_where(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    outcome = run_workspace_script(
        workspace,
        "ree-scripts/step.sh",
        log=_quiet(),
        launch=Launch(script=RESERVED_LAUNCH_SCRIPT),
    )
    assert outcome.status == "succeeded"
    assert (workspace / "ran-in.txt").read_text() == "4711\n"
    assert outcome.launched is not None
    assert (outcome.launched.node, outcome.launched.slurm_job_id, outcome.launched.slurm_step_id) == (
        platform.node(),
        "4711",
        "0",
    )
    # The record it was read from is a control file, gone once read.
    assert not list(workspace.glob(f"{RECORD_PREFIX}*"))


def test_a_reviewers_options_reach_the_launch_script(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    launch = Launch(script=RESERVED_LAUNCH_SCRIPT, options=(LaunchOption("--partition=short"), LaunchOption("-c4")))
    run_workspace_script(workspace, "ree-scripts/step.sh", log=_quiet(), launch=launch)
    assert (workspace / "launch-options.txt").read_text() == "--partition=short -c4\n"


def test_without_a_launch_a_script_runs_directly_and_records_nowhere(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    outcome = run_workspace_script(workspace, "ree-scripts/step.sh", log=_quiet())
    assert outcome.status == "succeeded"
    assert (workspace / "ran-in.txt").read_text() == "none\n"
    assert outcome.launched is None


def test_a_launch_that_never_runs_the_command_records_nowhere(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / RESERVED_LAUNCH_SCRIPT).write_text("exit 0\n")
    outcome = run_workspace_script(
        workspace,
        "ree-scripts/step.sh",
        log=_quiet(),
        launch=Launch(script=RESERVED_LAUNCH_SCRIPT),
    )
    assert outcome.launched is None
    assert not (workspace / "ran-in.txt").exists()


def test_the_declared_launch_is_used_only_while_its_script_is_the_one_declared(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    body = FAKE_SRUN.encode()
    definition = LaunchDefinition(launch_script_digest=digest_bytes(body), launch_script_size=len(body))
    assert declared_launch(definition, workspace) == Launch(script=RESERVED_LAUNCH_SCRIPT)
    (workspace / RESERVED_LAUNCH_SCRIPT).write_text(FAKE_SRUN + "# edited\n")
    with pytest.raises(ReePreconditionError, match="does not match"):
        declared_launch(definition, workspace)
