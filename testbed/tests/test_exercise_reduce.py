from pathlib import Path

import pytest

from repo2ree_testbed.exercise import Exercise, InitializeRee
from repo2ree_testbed.exercise_case import (
    CaseCoverage,
    Conforms,
    CoveredFile,
    ExerciseCase,
    HandWritten,
    NewArcs,
    Reached,
    Searched,
    ShowedProblems,
    Shows,
    blobs,
    cases,
    write,
)
from repo2ree_testbed.exercise_verdict import Problem
from repo2ree_testbed.runs.exercise_reduce import main, reduce

FILE = "testbed/src/repo2ree_testbed/runs/exercise_reduce.py"
PROBLEM = Problem(kind="violated", rule="machine:Attempt", subject="Attempt a")


def case(
    name: str,
    steps: int,
    reached: tuple[str, ...] = (),
    arcs: tuple[tuple[int, int], ...] = (),
    *,
    written: bool = False,
    problem: bool = False,
) -> ExerciseCase:
    exercise = Exercise(rees=("author",), steps=tuple(InitializeRee(ree="author", name=name) for _ in range(steps)))
    origin = (
        HandWritten()
        if written
        else Searched(search="branch-cov", run="run", commit="c", dirty=False, kept_for=NewArcs(files={FILE: 1}))
    )
    if problem and not written:
        origin = origin.model_copy(update={"kept_for": ShowedProblems()})
    coverage = CaseCoverage(
        commit="c", dirty=False, files={FILE: CoveredFile(blob=blobs((FILE,))[FILE] or "", arcs=arcs)}
    )
    return ExerciseCase(
        exercise=exercise,
        origin=origin,
        expects=Shows(problems=(PROBLEM,)) if problem else Conforms(),
        reached=Reached(spec_digest="sha256:spec", items=reached),
        coverage=coverage,
    )


def test_a_searched_case_reaching_and_covering_nothing_beyond_the_others_is_removed() -> None:
    written = case("written", 2, ("evidence",), ((1, 2),), written=True)
    wider = case("wider", 3, ("evidence", "review"), ((1, 2), (2, 3)))
    narrower = case("narrower", 2, ("review",), ((2, 3),))

    reduction = reduce([written, wider, narrower])

    assert [found.digest for found in reduction.removed] == [wider.digest]
    assert {found.digest for found in reduction.kept} == {written.digest, narrower.digest}


def test_spec_reach_and_branch_coverage_each_keep_a_case() -> None:
    reaching = case("reaching", 2, ("review",), ((1, 2),))
    covering = case("covering", 2, ("evidence",), ((5, 6),))
    both = case("both", 4, ("evidence",), ((1, 2),))

    reduction = reduce([reaching, covering, both])

    assert {found.digest for found in reduction.kept} == {reaching.digest, covering.digest}


def test_of_equal_cases_the_one_with_fewer_steps_stays() -> None:
    longer = case("longer", 5, ("evidence",), ((1, 2),))
    shorter = case("shorter", 2, ("evidence",), ((1, 2),))

    reduction = reduce([longer, shorter])

    assert [found.digest for found in reduction.kept] == [shorter.digest]


def test_a_hand_written_case_stays_though_it_adds_nothing() -> None:
    written = case("written", 3, ("evidence",), ((1, 2),), written=True)
    searched = case("searched", 2, ("evidence", "review"), ((1, 2), (2, 3)))

    assert reduce([written, searched]).removed == ()


def test_a_problem_no_kept_case_names_any_longer_is_reported() -> None:
    wider = case("wider", 3, ("evidence",), ((1, 2),))
    showing = case("showing", 4, ("evidence",), ((1, 2),), problem=True)

    reduction = reduce([wider, showing])

    assert reduction.unnamed == (PROBLEM.known_as,)


def test_the_redundant_cases_and_their_coverage_are_deleted(tmp_path: Path) -> None:
    kept = case("kept", 3, ("evidence",), ((1, 2),))
    redundant = case("redundant", 4, ("evidence",), ((1, 2),))
    for found in (kept, redundant):
        write(found, tmp_path)

    assert main(["--cases", str(tmp_path), "--dry-run"]) == 0
    assert len(cases(tmp_path)) == 2
    assert main(["--cases", str(tmp_path)]) == 0

    assert [found.digest for found in cases(tmp_path)] == [kept.digest]
    assert not (tmp_path / "coverage" / f"{redundant.digest}.json").exists()


def test_without_current_coverage_nothing_is_removed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    unmeasured = case("unmeasured", 3, ("evidence",)).model_copy(update={"coverage": None})
    write(unmeasured, tmp_path)
    write(case("redundant", 4, ("evidence",)), tmp_path)

    assert main(["--cases", str(tmp_path)]) == 1

    assert len(cases(tmp_path)) == 2
    assert "re-measure-exercise-branch-cov" in capsys.readouterr().err
