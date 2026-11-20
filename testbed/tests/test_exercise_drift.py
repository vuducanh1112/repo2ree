"""A drift replayed through ree: the environment changes an REE's file between two commands, journals it, and the
checker holds the next attempt to having found it."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_testbed.api_models import DefinitionPatch
from repo2ree_testbed.exercise import (
    Drift,
    Exercise,
    InitializeRee,
    MaterializeWorkspace,
    PatchReeDefinition,
)
from repo2ree_testbed.exercise_case import CASES, ExerciseCase
from repo2ree_testbed.exercise_verdict import judge

RULE = "drift-is-found-by-the-next-attempt"
LAUNCH = "ree-scripts/launch.sh"


def drifted(path: str) -> Exercise:
    return Exercise(
        rees=("author",),
        steps=(
            InitializeRee(ree="author"),
            MaterializeWorkspace(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="renamed")),
        ),
        drifts=(Drift(before=2, ree="author", path=path, content="#!/bin/sh\necho drifted\n"),),
    )


def test_a_file_changed_in_the_workspace_is_refused_by_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(f"workspace/{LAUNCH}"), tmp_path)

    patched = trace.replayed[2].ran
    assert patched is not None
    assert isinstance(patched.result, dict)
    failure = patched.result["failure"]
    assert patched.result["status"] == "failed"
    assert isinstance(failure, dict)
    assert failure["details"] == {"code": "drift"}
    assert RULE in trace.reached
    assert [problem for problem in trace.problems if problem.rule == RULE] == []


def test_a_script_edited_in_the_overlay_is_recorded_before_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(f"overlay/{LAUNCH}"), tmp_path)

    patched = trace.replayed[2].ran
    assert patched is not None
    assert isinstance(patched.result, dict)
    assert patched.result["status"] == "succeeded"
    assert RULE in trace.reached
    assert [problem for problem in trace.problems if problem.rule == RULE] == []


def test_an_ree_no_step_initialized_yet_does_not_drift() -> None:
    steps = (InitializeRee(ree="author"),)
    with pytest.raises(ValueError, match="before any step initialized it"):
        Exercise(rees=("author",), steps=steps, drifts=(Drift(before=0, ree="author", path="workspace/x"),))
    with pytest.raises(ValueError, match="no file of an REE"):
        Drift(before=1, ree="author", path="../outside")
    assert Exercise(rees=("author",), steps=steps, drifts=(Drift(before=1, ree="author", path="workspace/x"),))


def test_every_kept_case_is_named_by_its_exercise_s_digest() -> None:
    kept = sorted(CASES.glob("*.json"))
    assert kept
    for path in kept:
        case = ExerciseCase.model_validate_json(path.read_text())
        assert path.stem == case.digest, (
            f"{path.name} holds the exercise named {case.digest}: rename it and its coverage"
        )
