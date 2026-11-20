"""The exercise cases in ``exercises/``, each replayed through ``ree``, one test per case: the e2e-cli tier.

A case must show what it expects: that each command answers as ``ree schema`` says it does and the histories conform
to the specification, or exactly the problems it names (see ``repo2ree_testbed.exercise_case``). In the tier, each
test runs ``ree`` on a machine the stack starts for it with no service on it, and keeps each REE's histories for the
behaviour check (``E2E_KEPT_REE_DIR``), with the journal it wrote as their environment (``E2E_KEPT_JOURNAL_DIR``),
which the assurance gate judges like any other test's; a case's expectation is
the gate's excuse for exactly the rules it names. Run on its own, it runs ``ree`` on this machine.

What a case reaches now, against what it recorded, and whether its code coverage holds for the code as it stands,
are reported as warnings, never as failures.
"""

from __future__ import annotations

import os
import shutil
import warnings
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.cli_machine import Machine, keep_histories
from repo2ree_testbed.exercise_case import CASES, ExerciseCase, cases, drifted, unmeasured, unmet
from repo2ree_testbed.exercise_cli import CliReplay, RunRee, local_ree, machine_ree
from repo2ree_testbed.exercise_verdict import judge, keep

DIRECTORY = Path(os.environ.get("EXERCISE_CASES", str(CASES)))
KEPT = os.environ.get("E2E_KEPT_REE_DIR")
KEPT_JOURNALS = os.environ.get("E2E_KEPT_JOURNAL_DIR")
TEST_DIR = os.environ.get("E2E_TEST_DIR")


@pytest.mark.parametrize("case", cases(DIRECTORY), ids=lambda case: case.digest)
def test_a_case_shows_what_it_expects(case: ExerciseCase) -> None:
    machine = Machine.of_this_test()
    run: RunRee = local_ree if machine is None else machine_ree(machine)
    workdir = (
        run_dir() / "exercises" / execution_id() / "replay" / case.digest
        if machine is None
        else machine.workdir / case.digest
    )
    shutil.rmtree(workdir, ignore_errors=True)
    trace = judge(case.exercise, workdir, run=run)
    if KEPT:
        for root in CliReplay(run, workdir).histories(case.exercise):
            keep_histories(root, Path(KEPT) / root.name)
    if KEPT_JOURNALS:
        shutil.copytree(CliReplay(run, workdir).journals, KEPT_JOURNALS, dirs_exist_ok=True)
    keep(workdir, trace)
    if TEST_DIR:
        artifacts = Path(TEST_DIR) / "artifacts" / "exercise"
        artifacts.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workdir / "trace.json", artifacts / "trace.json")
        shutil.copytree(workdir / "check", artifacts / "check", dirs_exist_ok=True)
    for told in (drifted(case, trace), unmeasured(case)):
        if told:
            warnings.warn(told, stacklevel=1)
    unmatched = unmet(case, trace)
    assert not unmatched, f"kept in {workdir}:\n" + "\n".join(unmatched)
