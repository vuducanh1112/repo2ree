import json
from pathlib import Path
from typing import get_args

from pydantic import JsonValue

from repo2ree_testbed.exercise import Exercise, InitializeRee
from repo2ree_testbed.exercise_case import HandWritten, case_of, cases, write
from repo2ree_testbed.exercise_cli import Ran, Replayed
from repo2ree_testbed.exercise_features import (
    ActionStatus,
    FailureCategory,
    InContext,
    Outcome,
    RuleOutcome,
    RuleTriggered,
    Transition,
    from_report,
    outcomes,
    placed,
)
from repo2ree_testbed.exercise_verdict import CLI_SCHEMA, Trace, schema_command

REPORT = {
    "rules": [
        {"rule": "machine:Attempt", "triggered": 2, "findings": [{"verdict": "violated", "subject": "Attempt a"}]},
        {"rule": "evidence", "triggered": 1, "findings": []},
        {"rule": "machine:Receipt", "triggered": 0, "findings": []},
    ],
    "coverage": {
        "transitions": {"Attempt": {"(none) -> pending": 2, "pending -> executing": 0}},
        "messages": {},
        "partitions": {
            "Attempt": {"author": {"(none) -> pending": 1}, "reviewer/reviews/first": {"(none) -> pending": 1}}
        },
    },
}


def test_the_cli_answers_features_name_are_those_its_schema_declares() -> None:
    schema = json.loads(CLI_SCHEMA.read_text())["$defs"]
    assert set(get_args(ActionStatus.__value__)) == set(schema["ActionResult"]["properties"]["status"]["enum"])
    assert set(get_args(FailureCategory.__value__)) == set(schema["Failure"]["properties"]["category"]["enum"])


def test_a_report_gives_the_rules_triggered_the_transitions_taken_where_and_each_rules_outcome() -> None:
    features = set(from_report(REPORT))

    assert features == {
        RuleTriggered(rule="machine:Attempt"),
        RuleTriggered(rule="evidence"),
        Transition(entity="Attempt", move="(none) -> pending"),
        InContext(entity="Attempt", move="(none) -> pending", ree="author", store="ree"),
        InContext(entity="Attempt", move="(none) -> pending", ree="reviewer", store="review"),
        RuleOutcome(rule="machine:Attempt", verdict="violated"),
        RuleOutcome(rule="machine:Attempt", verdict="held"),
        RuleOutcome(rule="evidence", verdict="held"),
    }


def test_a_partition_is_placed_in_its_ree_and_store() -> None:
    assert placed("author") == ("author", "ree")
    assert placed("reviewer/reviews/first") == ("reviewer", "review")
    assert placed("") == (None, "ree")


def test_each_command_answers_with_its_exit_status_and_failure_category_or_no_result() -> None:
    failed: JsonValue = {"status": "failed", "failure": {"category": "precondition", "message": "seal it first"}}
    replayed = (
        Replayed(step=0, ree="author", operation="initialize_ree", ran=Ran(words=("initialize-ree",), exit=0)),
        Replayed(step=1, ree="author", operation="sign_ree", ran=Ran(words=("sign-ree",), exit=2, result=failed)),
    )

    assert set(outcomes(replayed, schema_command)) == {
        Outcome(command="initialize-ree", ree="author", exit=0, status=None, category=None),
        Outcome(command="sign-ree", ree="author", exit=2, status="failed", category="precondition"),
    }


def test_a_case_is_read_back_with_every_feature_it_was_written_with(tmp_path: Path) -> None:
    features = (
        Outcome(command="initialize-ree", ree="author", exit=0),
        InContext(entity="Attempt", move="(none) -> pending", store="ree"),
        *from_report(REPORT),
    )
    exercise = Exercise(rees=("author",), steps=(InitializeRee(ree="author", name="x"),))
    trace = Trace(exercise=exercise, replayed=(), problems=(), features=features, spec_digest="sha256:spec")
    write(case_of(trace, HandWritten()), tmp_path)

    [case] = cases(tmp_path)

    assert set(case.features.features) == set(features)
