from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_case import (
    Campaign,
    CampaignSettings,
    KeptCase,
    NewArcs,
    NewFeatures,
    Searched,
    Shows,
    cases,
)
from repo2ree_testbed.exercise_features import RuleTriggered
from repo2ree_testbed.exercise_verdict import Problem, Trace
from repo2ree_testbed.runs.search import Event, Judge, Kept, RoundEnded, Search, Unconfirmed, run, summed

COVERED = "testbed/src/repo2ree_testbed/runs/search.py"
PROBLEM = Problem(kind="violated", rule="machine:Attempt", subject="Attempt a")
SHALLOW, DEEP = RuleTriggered(rule="shallow"), RuleTriggered(rule="deep")


@pytest.fixture(autouse=True)
def artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO2REE_TEST_RUN_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("REPO2REE_TEST_RUN_ID", "run-under-test")


def deep_from(steps: int, *, problem: bool = False, arcs: bool = False) -> Judge:
    def judged(exercise: Exercise, _workdir: Path, measured: bool) -> Trace:
        deep = len(exercise.steps) >= steps
        return Trace(
            exercise=exercise,
            replayed=(),
            problems=(PROBLEM,) if deep and problem else (),
            features=(DEEP, SHALLOW) if deep else (SHALLOW,),
            spec_digest="sha256:spec",
            arcs=({COVERED: ((1, 2), (2, 3)) if deep and arcs else ((1, 2),)} if measured else None),
        )

    return judged


def searching(tmp_path: Path, **given: object) -> Search:
    search = Search(search="spec-cov", directory=tmp_path / "cases", examples=60, steps=8, least=1, judge=deep_from(3))
    for name, value in given.items():
        setattr(search, name, value)
    search.features = frozenset({SHALLOW})
    search.arcs = {COVERED: ((1, 2),)}
    return search


def test_an_exercise_reaching_what_no_case_reaches_is_kept_shrunk_to_the_fewest_steps(tmp_path: Path) -> None:
    search = searching(tmp_path)

    found = search.round()
    assert found is not None
    path = search.confirm(found)

    assert path is not None
    [case] = cases(tmp_path / "cases")
    assert len(case.exercise.steps) == 3
    assert isinstance(case.origin, Searched)
    assert case.origin.search == "spec-cov"
    assert case.origin.kept_for == NewFeatures(features=(DEEP,))
    assert case.features.features == (DEEP, SHALLOW)
    assert search.round() is None


def test_an_exercise_covering_something_new_while_showing_a_problem_is_kept_expecting_it(tmp_path: Path) -> None:
    search = searching(tmp_path, judge=deep_from(2, problem=True))

    found = search.round()
    assert found is not None
    search.confirm(found)

    [case] = cases(tmp_path / "cases")
    assert len(case.exercise.steps) == 2
    assert isinstance(case.origin, Searched)
    assert case.origin.kept_for == NewFeatures(features=(DEEP,))
    assert isinstance(case.expects, Shows)


def test_an_exercise_executing_arcs_no_case_covers_is_kept_with_its_coverage(tmp_path: Path) -> None:
    search = searching(tmp_path, search="branch-cov", judge=deep_from(4, arcs=True))

    found = search.round()
    assert found is not None
    search.confirm(found)

    [case] = cases(tmp_path / "cases")
    assert len(case.exercise.steps) == 4
    assert isinstance(case.origin, Searched)
    assert case.origin.kept_for == NewArcs(files={COVERED: 1})
    assert case.coverage is not None
    assert case.coverage.files[COVERED].arcs == ((1, 2), (2, 3))


def test_a_find_that_does_not_hold_when_replayed_again_is_not_kept(tmp_path: Path) -> None:
    search = searching(tmp_path)
    found = search.round()
    assert found is not None
    search.judge = deep_from(99)

    assert search.confirm(found) is None
    assert cases(tmp_path / "cases") == ()


def test_a_search_without_hours_runs_one_round_and_keeps_at_most_what_it_may(tmp_path: Path) -> None:
    search = searching(tmp_path)

    assert run(search, until=None, keep_at_most=5) == 0
    assert len(cases(tmp_path / "cases")) == 1


def test_a_search_keeping_a_problem_ends_failed(tmp_path: Path) -> None:
    search = searching(tmp_path, judge=deep_from(2, problem=True))

    assert run(search, until=None, keep_at_most=5) == 1


def test_a_find_another_search_kept_meanwhile_is_not_kept_again(tmp_path: Path) -> None:
    first, second = searching(tmp_path), searching(tmp_path)
    found_first, found_second = first.round(), second.round()
    assert found_first is not None
    assert found_second is not None

    assert first.confirm(found_first) is not None
    assert second.confirm(found_second) is None
    assert len(cases(tmp_path / "cases")) == 1


def test_a_campaign_sums_its_rounds_and_the_cases_it_kept() -> None:
    settings = CampaignSettings(examples=5, steps=4, keep=3, least=1, hours=None, workers=2)
    started = Campaign(
        run="run",
        search="spec-cov",
        settings=settings,
        commit="c",
        dirty=False,
        machine="vm",
        started=datetime.now(UTC),
    )
    kept = NewFeatures(features=(DEEP,))
    events: list[Event] = [
        RoundEnded(worker=0, round=1, found=True, seconds=1.0),
        Kept(worker=0, case="abc", steps=3, kept_for=kept),
        RoundEnded(worker=1, round=1, found=True, seconds=1.0),
        Unconfirmed(worker=1, digest="abc", why="kept meanwhile"),
        RoundEnded(worker=1, round=2, found=False, seconds=1.0),
    ]

    ended = summed(started, events, 0)

    assert (ended.rounds, ended.rounds_found, ended.unconfirmed, ended.exit) == (3, 2, 1, 0)
    assert ended.kept == (KeptCase(case="abc", kept_for=kept, steps=3, worker=0),)
    assert ended.ended is not None
