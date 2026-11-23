from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.showcases import ProjectName

AUTHOR_THEN_REVIEW: dict[str, Any] = {
    "rees": ["author", "reviewer"],
    "steps": [
        {"ree": "author", "operation": "initialize_ree"},
        {"ree": "reviewer", "operation": "initialize_ree", "name": "a-reviewer"},
        {"ree": "author", "operation": "acquire_source", "source": {"kind": "uploaded", "project": "python_venv"}},
        {
            "ree": "author",
            "operation": "write_script",
            "script": "build_experiment_environment",
            "content": {"kind": "recipe", "project": "python_venv", "file": "build_experiment_environment.sh"},
        },
        {
            "ree": "author",
            "operation": "write_script",
            "script": "experiment_verify",
            "experiment": "python-pip-hello",
            "content": {"kind": "text", "text": "exit 0\n"},
        },
        {"ree": "author", "operation": "build_experiment_environment"},
        {"ree": "author", "operation": "seal_ree"},
        {"ree": "author", "operation": "sign_ree", "signature": "foreign_key"},
        {"ree": "reviewer", "operation": "load_ree_bundle", "exported_by": "author"},
        {"ree": "reviewer", "operation": "review_acquire_source", "review": "r1", "basis": "bundled"},
        {"ree": "reviewer", "operation": "sign_review", "review": "r1"},
    ],
    "faults": [{"step": 5, "kind": "kill", "at": "completed"}, {"step": 6, "kind": "no_space", "at": "executing"}],
}


def stepped(*steps: dict[str, Any], **exercise: Any) -> dict[str, Any]:
    return {"rees": ["author", "reviewer"], "steps": list(steps)} | exercise


def test_an_exercise_round_trips_as_json_and_keeps_its_format() -> None:
    exercise = Exercise.model_validate(AUTHOR_THEN_REVIEW)
    assert exercise.format == "repo2ree-exercise/1"
    assert Exercise.model_validate_json(exercise.model_dump_json()) == exercise
    assert exercise.steps[2].source.project == ProjectName.PYTHON_VENV  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("exercise", "message"),
    [
        (stepped({"ree": "stranger", "operation": "seal_ree"}), "runs in stranger"),
        (stepped({"ree": "author", "operation": "load_ree_bundle", "exported_by": "author"}), "no other REE"),
        (
            stepped(
                {"ree": "author", "operation": "seal_ree"}, faults=[{"step": 1, "kind": "no_space", "at": "pending"}]
            ),
            "no step",
        ),
        (
            stepped(
                {"ree": "author", "operation": "seal_ree"},
                faults=[
                    {"step": 0, "kind": "no_space", "at": "pending"},
                    {"step": 0, "kind": "history_locked", "at": "pending"},
                ],
            ),
            "two faults",
        ),
        (
            stepped({"ree": "author", "operation": "seal_ree"}, faults=[{"step": 0, "kind": "kill", "at": "captured"}]),
            "Input should be 'pending', 'executing' or 'completed'",
        ),
        (
            stepped(
                {
                    "ree": "author",
                    "operation": "write_script",
                    "script": "experiment_run",
                    "content": {"kind": "text", "text": ""},
                }
            ),
            "names experiment",
        ),
        (
            stepped(
                {
                    "ree": "author",
                    "operation": "write_script",
                    "script": "launch",
                    "experiment": "e",
                    "content": {"kind": "text", "text": ""},
                }
            ),
            "names no experiment",
        ),
        ({"rees": ["a", "a"], "steps": []}, "named twice"),
        ({"rees": [], "steps": []}, "at least 1"),
        (stepped({"ree": "author", "operation": "no_such_operation"}), "does not match any of the expected tags"),
    ],
)
def test_an_exercise_refuses_what_it_does_not_hold(exercise: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Exercise.model_validate(exercise)
