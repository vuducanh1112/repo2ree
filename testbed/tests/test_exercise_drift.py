"""A drift replayed through ree: the environment changes an REE's file between two commands, journals it, and the
checker holds the next attempt to having found it."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from repo2ree_testbed.api_models import DefinitionPatch
from repo2ree_testbed.exercise import (
    Drift,
    Exercise,
    FileDrift,
    HistoryChange,
    HistoryDrift,
    InitializeRee,
    LoadReeBundle,
    MaterializeWorkspace,
    PatchReeDefinition,
)
from repo2ree_testbed.exercise_case import CASES, ExerciseCase
from repo2ree_testbed.exercise_verdict import Trace, judge

RULE = "drift-is-found-by-the-next-attempt"


def drifted(drift: Drift) -> Exercise:
    return Exercise(
        rees=("author",),
        steps=(
            InitializeRee(ree="author"),
            MaterializeWorkspace(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="renamed")),
        ),
        drifts=(drift,),
    )


def answered(trace: Trace, step: int) -> dict[str, JsonValue]:
    ran = trace.replayed[step].ran
    assert ran is not None
    assert isinstance(ran.result, dict)
    return ran.result


def found(trace: Trace) -> None:
    assert RULE in trace.reached
    assert [problem for problem in trace.problems if problem.rule == RULE] == []


def test_a_file_changed_in_the_workspace_is_refused_by_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(FileDrift(before=2, ree="author", part="workspace", change="append")), tmp_path)

    patched = answered(trace, 2)
    assert patched["status"] == "failed"
    assert isinstance(patched["failure"], dict)
    assert patched["failure"]["details"] == {"code": "drift"}
    found(trace)


def test_a_script_edited_in_the_overlay_is_recorded_before_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(FileDrift(before=2, ree="author", part="overlay", change="write")), tmp_path)

    assert answered(trace, 2)["status"] == "succeeded"
    found(trace)


@pytest.mark.parametrize("change", ["commit", "amend", "reset"])
def test_a_history_changed_by_git_is_refused_until_it_is_put_back(tmp_path: Path, change: HistoryChange) -> None:
    exercise = Exercise(
        rees=("author",),
        steps=(
            InitializeRee(ree="author"),
            MaterializeWorkspace(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="refused")),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="put-back")),
        ),
        drifts=(HistoryDrift(before=2, ree="author", change=change, until=3),),
    )
    trace = judge(exercise, tmp_path)

    assert answered(trace, 2)["status"] == "failed"
    assert answered(trace, 3)["status"] == "succeeded"
    found(trace)
    assert [problem for problem in trace.problems if problem.kind == "violated"] == []


def test_an_ree_no_step_initialized_yet_does_not_drift() -> None:
    steps = (InitializeRee(ree="author"),)
    early = FileDrift(before=0, ree="author", part="workspace", change="add")
    with pytest.raises(ValueError, match="before any step initialized it"):
        Exercise(rees=("author",), steps=steps, drifts=(early,))
    with pytest.raises(ValueError, match="none of the REE's"):
        FileDrift(before=1, ree="author", part="records", change="add")
    assert Exercise(rees=("author",), steps=steps, drifts=(early.model_copy(update={"before": 1}),))


def test_every_kept_case_is_named_by_its_exercise_s_digest() -> None:
    kept = sorted(CASES.glob("*.json"))
    assert kept
    for path in kept:
        case = ExerciseCase.model_validate_json(path.read_text())
        assert path.stem == case.digest, (
            f"{path.name} holds the exercise named {case.digest}: rename it and its coverage"
        )


BUNDLE = "bundles-carry-what-attempts-captured"


def test_a_bundle_is_journaled_with_the_heads_it_carries(tmp_path: Path) -> None:
    exercise = Exercise(
        rees=("author", "other"),
        steps=(
            InitializeRee(ree="author"),
            InitializeRee(ree="other"),
            LoadReeBundle(ree="other", exported_by="author"),
        ),
    )
    trace = judge(exercise, tmp_path)

    assert BUNDLE in trace.reached
    assert [problem for problem in trace.problems if problem.rule == BUNDLE] == []
