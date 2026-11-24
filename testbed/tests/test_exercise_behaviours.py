import json
from pathlib import Path
from typing import get_args

from pydantic import JsonValue

from repo2ree_testbed.exercise import Exercise, InitializeRee
from repo2ree_testbed.exercise_behaviours import (
    ActionStatus,
    FailureCategory,
    Move,
    Outcome,
    Verdict,
    declared,
    from_report,
    outcomes,
)
from repo2ree_testbed.exercise_case import HandWritten, case_of, cases, write
from repo2ree_testbed.exercise_cli import Ran, Replayed
from repo2ree_testbed.exercise_verdict import CLI_SCHEMA, Trace, schema_command

REPORT = {
    "rules": [
        {"rule": "machine:Attempt", "triggered": 2, "findings": [{"verdict": "violated", "subject": "Attempt a"}]},
        {"rule": "evidence", "triggered": 1, "findings": []},
        {"rule": "machine:Receipt", "triggered": 0, "findings": []},
    ],
    "aggregates": [
        {
            "aggregate": "Ree",
            "moves": [
                {
                    "kind": "field",
                    "machine": "definition.source",
                    "operation": "acquire_source",
                    "source": "unset",
                    "target": "set",
                    "count": 1,
                    "allowed": True,
                },
                {
                    "kind": "lifecycle",
                    "machine": "lifecycle",
                    "operation": "seal_ree",
                    "source": "draft",
                    "target": "sealed",
                    "count": 1,
                    "allowed": True,
                },
                {
                    "kind": "receipt",
                    "machine": "acquire_source",
                    "operation": "acquire_source",
                    "source": "missing",
                    "target": "current",
                    "count": 1,
                    "allowed": True,
                },
                {
                    "kind": "field",
                    "machine": "definition.hbom",
                    "operation": "observe_hardware",
                    "source": "unset",
                    "target": "set",
                    "count": 0,
                    "allowed": True,
                },
            ],
        }
    ],
}
SOURCE_SET = Move(
    aggregate="Ree", machine="definition.source", part="field", operation="acquire_source", source="unset", target="set"
)
SEALED = Move(
    aggregate="Ree", machine="lifecycle", part="lifecycle", operation="seal_ree", source="draft", target="sealed"
)


def test_the_cli_answers_behaviours_name_are_those_its_schema_declares() -> None:
    schema = json.loads(CLI_SCHEMA.read_text())["$defs"]
    assert set(get_args(ActionStatus.__value__)) == set(schema["ActionResult"]["properties"]["status"]["enum"])
    assert set(get_args(FailureCategory.__value__)) == set(schema["Failure"]["properties"]["category"]["enum"])


def test_a_report_gives_each_rules_verdicts_and_each_lifecycle_and_field_edge_taken_by_its_operation() -> None:
    assert set(from_report(REPORT)) == {
        Verdict(rule="machine:Attempt", verdict="violated"),
        Verdict(rule="machine:Attempt", verdict="held"),
        Verdict(rule="evidence", verdict="held"),
        SOURCE_SET,
        SEALED,
    }


def test_the_specification_declares_each_cli_core_rule_held_and_each_edge_by_each_operation_it_names() -> None:
    spec = {
        "cli_core": {"entities": ["Ree"], "rules": ["evidence", "aggregate:Ree"]},
        "aggregates": {
            "Ree": {
                "machines": [
                    {
                        "kind": "lifecycle",
                        "name": "lifecycle",
                        "edges": [{"from": "draft", "to": "sealed", "by": ["seal_ree"]}],
                    },
                    {
                        "kind": "field",
                        "name": "definition.source",
                        "edges": [{"from": "unset", "to": "set", "by": ["acquire_source", "load_ree_bundle"]}],
                    },
                    {
                        "kind": "receipt",
                        "name": "acquire_source",
                        "edges": [{"from": "missing", "to": "current", "by": ["acquire_source"]}],
                    },
                ]
            },
            "Elsewhere": {
                "machines": [
                    {"kind": "lifecycle", "name": "lifecycle", "edges": [{"from": "a", "to": "b", "by": ["x"]}]}
                ]
            },
        },
    }

    assert set(declared(spec)) == {
        Verdict(rule="evidence", verdict="held"),
        Verdict(rule="aggregate:Ree", verdict="held"),
        SEALED,
        SOURCE_SET,
        SOURCE_SET.model_copy(update={"operation": "load_ree_bundle"}),
    }


def test_each_command_answers_with_its_status_and_failure_category_or_no_result() -> None:
    failed: JsonValue = {"status": "failed", "failure": {"category": "precondition", "message": "seal it first"}}
    replayed = (
        Replayed(step=0, ree="author", operation="initialize_ree", ran=Ran(words=("initialize-ree",), exit=0)),
        Replayed(step=1, ree="author", operation="sign_ree", ran=Ran(words=("sign-ree",), exit=2, result=failed)),
    )

    assert set(outcomes(replayed, schema_command)) == {
        Outcome(command="initialize-ree", status=None, category=None),
        Outcome(command="sign-ree", status="failed", category="precondition"),
    }


def test_a_case_is_read_back_with_every_behaviour_it_was_written_with(tmp_path: Path) -> None:
    behaviours = (
        Outcome(command="initialize-ree"),
        *from_report(REPORT),
    )
    exercise = Exercise(rees=("author",), steps=(InitializeRee(ree="author", name="x"),))
    trace = Trace(exercise=exercise, replayed=(), problems=(), behaviours=behaviours, spec_digest="sha256:spec")
    write(case_of(trace, HandWritten()), tmp_path)

    [case] = cases(tmp_path)

    assert set(case.behaviours.behaviours) == set(behaviours)
