"""Exercises replayed through ``ree`` on this machine: the cases in ``exercises/``, and as many more as Hypothesis
draws.

Whatever an exercise's steps, each command answers as ``ree schema`` says it does, and the histories it leaves
conform to the specification. A case must show what it expects: to conform, or exactly the problems it names (see
``repo2ree_testbed.exercise_case``). What a case reaches now, against what it recorded, is reported as a warning.

The searches (``-m property``) shrink an exercise that shows a problem no case names, and keep it as a case expecting
those problems, in ``exercises/`` unless ``EXERCISE_CASES`` names another directory. A problem a case names already
passes, so a known one does not stop a search. Two searches draw the same exercises and differ in what steers them
(``hypothesis.target``): one toward the rules and transitions of the specification, which any implementation of it
reaches alike; one toward the arcs this implementation executes beyond those the cases cover, measured by coverage.py
under the repo's configuration. The branch search measures the cases whose coverage is stale first, so it steers past
what they cover as the code stands; once it ends, it keeps up to ``EXERCISE_KEEP`` exercises that conformed as new
cases, each adding the most arcs beyond the cases and those kept before it, and each confirmed by a second measured
replay.

Every exercise judged leaves its trace under the run's ``exercises/<run>/<search>/<digest>/``: ``trace.json`` (the
exercise, what each command answered, its problems, the rules and transitions it reached, and the arcs it executed
when measured: which, file by file), the checker's reports in ``check/``, and in the branch search the coverage data
in ``coverage/``. ``exercises/<run>/<search>/coverage.ndjson`` lists, exercise by exercise, what each reached and what
of it no exercise before it had; ``covered.json`` holds what they reached together. An exercise that shows a problem
keeps its REEs too.
"""

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
    ExerciseCase,
    NewArcs,
    SearchName,
    ShowedProblems,
    adding,
    case_of,
    cases,
    coverage_of,
    covered,
    drifted,
    known,
    measure,
    searched,
    unmeasured,
    unmet,
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


def judged(exercise: Exercise, search: Literal["replay", "confirm"] | SearchName = "replay") -> tuple[Trace, Path]:
    """Replay and judge ``exercise`` in a directory of its own under this run's and this search's, and keep its trace
    there; the branch search measures what ree executed."""
    workdir = run_dir() / "exercises" / execution_id() / search / digest(exercise)
    shutil.rmtree(workdir, ignore_errors=True)
    trace = judge(exercise, workdir, measured=search in {"branch-cov", "confirm"})
    keep(workdir, trace)
    return trace, workdir


@pytest.mark.parametrize("case", cases(DIRECTORY), ids=lambda case: case.digest)
def test_a_case_shows_what_it_expects(case: ExerciseCase) -> None:
    trace, workdir = judged(case.exercise)
    for told in (drifted(case, trace), unmeasured(case)):
        if told:
            warnings.warn(told, stacklevel=1)
    unmatched = unmet(case, trace)
    assert not unmatched, f"kept in {workdir}:\n" + "\n".join(unmatched)


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


# What the branch search steers past, and the exercises it may keep: set when it starts.
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
    """What the cases cover as the code stands: the stale and unmeasured ones measured again first."""
    for case in cases(DIRECTORY):
        if unmeasured(case):
            workdir = run_dir() / "exercises" / execution_id() / "baseline" / case.digest
            shutil.rmtree(workdir, ignore_errors=True)
            measure(case, workdir, DIRECTORY)
    return covered(cases(DIRECTORY))


def _keep_new_arcs() -> list[Path]:
    """Keep as cases the candidates that add the most arcs beyond the baseline, each confirmed by a second measured
    replay: only the arcs it adds again, beyond the baseline and the cases kept before it, count, and one that no
    longer conforms or adds nothing is not kept."""
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
    """Run the search ``run``; the exercise it shrinks to is kept as a case expecting its problems before the test
    fails with it."""
    try:
        run()
    except NonconformingError as found:
        trace = found.trace
        coverage = coverage_of(trace.arcs) if trace.arcs is not None else None
        path = write(case_of(trace, searched(search, execution_id(), ShowedProblems()), coverage), DIRECTORY)
        raise AssertionError(f"kept as {path}:\n{found}") from found


@pytest.mark.property
def test_any_exercise_conforms_steered_by_spec_coverage() -> None:
    """The search steered toward the rules and transitions of the specification: what any implementation reaches."""
    _keeping("spec-cov", _toward_spec_coverage)


@pytest.mark.property
def test_any_exercise_conforms_steered_by_branch_coverage() -> None:
    """The search steered toward the arcs this implementation executes beyond what the cases cover: what the
    specification alone does not tell apart. What it keeps for new arcs is kept whether or not it found a problem."""
    BASELINE.clear()
    BASELINE.update(_baseline())
    CANDIDATES.clear()
    try:
        _keeping("branch-cov", _toward_branch_coverage)
    finally:
        for path in _keep_new_arcs():
            warnings.warn(f"kept for new arcs: {path}", stacklevel=1)
