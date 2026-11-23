from __future__ import annotations

import os
import shutil
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pytest
from hypothesis import HealthCheck, given, note, settings, target

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_case import (
    CASES,
    NewArcs,
    SearchName,
    ShowedProblems,
    adding,
    case_of,
    cases,
    coverage_of,
    covered,
    known,
    measure,
    searched,
    unmeasured,
    write,
)
from repo2ree_testbed.exercise_strategy import exercises
from repo2ree_testbed.exercise_verdict import Arcs, Trace, arc_count, arcs_union, arcs_without, digest, judge, keep

DIRECTORY = Path(os.environ.get("EXERCISE_CASES", str(CASES)))
EXAMPLES = int(os.environ.get("EXERCISE_EXAMPLES", "25"))
STEPS = int(os.environ.get("EXERCISE_STEPS", "30"))
KEEP = int(os.environ.get("EXERCISE_KEEP", "3"))


class NonconformingError(AssertionError):
    def __init__(self, trace: Trace, workdir: Path) -> None:
        self.trace = trace
        super().__init__(f"kept in {workdir}:\n" + "\n".join(map(str, trace.problems)))


def judged(exercise: Exercise, search: Literal["confirm"] | SearchName) -> tuple[Trace, Path]:
    workdir = run_dir() / "exercises" / execution_id() / search / digest(exercise)
    shutil.rmtree(workdir, ignore_errors=True)
    trace = judge(exercise, workdir, measured=search in {"branch-cov", "confirm"})
    keep(workdir, trace)
    return trace, workdir


KNOWN = known(DIRECTORY)

searching = settings(
    max_examples=EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    report_multiple_bugs=False,
)


def _unknown(trace: Trace, workdir: Path) -> None:
    if any(problem.known_as not in KNOWN for problem in trace.problems):
        raise NonconformingError(trace, workdir)


@searching
@given(exercises(max_steps=STEPS))
def _toward_spec_coverage(exercise: Exercise) -> None:
    note(exercise.model_dump_json(indent=2))
    trace, workdir = judged(exercise, "spec-cov")
    target(len(trace.reached), label="rules and transitions reached")
    _unknown(trace, workdir)


BASELINE: Arcs = {}
CANDIDATES: list[Trace] = []


@searching
@given(exercises(max_steps=STEPS))
def _toward_branch_coverage(exercise: Exercise) -> None:
    note(exercise.model_dump_json(indent=2))
    trace, workdir = judged(exercise, "branch-cov")
    beyond = arc_count(arcs_without(trace.arcs or {}, BASELINE))
    target(beyond, label="arcs ree executed beyond the cases")
    if beyond and not trace.problems:
        CANDIDATES.append(trace)
    _unknown(trace, workdir)


def _baseline() -> Arcs:
    for case in cases(DIRECTORY):
        if unmeasured(case):
            workdir = run_dir() / "exercises" / execution_id() / "baseline" / case.digest
            shutil.rmtree(workdir, ignore_errors=True)
            measure(case, workdir, DIRECTORY)
    return covered(cases(DIRECTORY))


def _keep_new_arcs() -> list[Path]:
    kept = []
    so_far = BASELINE
    for first, gained in adding(CANDIDATES, BASELINE, KEEP):
        again, _ = judged(first.exercise, "confirm")
        regained = arcs_without(again.arcs or {}, so_far)
        confirmed = arcs_without(gained, arcs_without(gained, regained))
        if again.problems or not arc_count(confirmed):
            continue
        so_far = arcs_union(so_far, confirmed)
        origin = searched(
            "branch-cov", execution_id(), NewArcs(files={path: len(pairs) for path, pairs in confirmed.items()})
        )
        kept.append(write(case_of(again, origin, coverage_of(again.arcs or {})), DIRECTORY))
    return kept


def _keeping(search: SearchName, run: Callable[[], None]) -> None:
    try:
        run()
    except NonconformingError as found:
        trace = found.trace
        coverage = coverage_of(trace.arcs) if trace.arcs is not None else None
        path = write(case_of(trace, searched(search, execution_id(), ShowedProblems()), coverage), DIRECTORY)
        raise AssertionError(f"kept as {path}:\n{found}") from found


@pytest.mark.property
def test_any_exercise_conforms_steered_by_spec_coverage() -> None:
    _keeping("spec-cov", _toward_spec_coverage)


@pytest.mark.property
def test_any_exercise_conforms_steered_by_branch_coverage() -> None:
    BASELINE.clear()
    BASELINE.update(_baseline())
    CANDIDATES.clear()
    try:
        _keeping("branch-cov", _toward_branch_coverage)
    finally:
        for path in _keep_new_arcs():
            warnings.warn(f"kept for new arcs: {path}", stacklevel=1)
