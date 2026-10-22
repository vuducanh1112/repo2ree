"""The specification page states each rule the way the specification writes it."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from repo2ree_repoview.overview.exports import Condition, Invariant, Spec
from repo2ree_repoview.overview.pages.specification import condition, requirement_text, rule_values, trigger_text

CONDITION = TypeAdapter[Condition](Condition)
GROUPS = {"result": {"success": ("ok",), "failure": ("error", "timeout")}}


def job(**changes: Any) -> dict[str, Any]:
    return {
        "name": "Job",
        "owner": "api",
        "key": "job_id",
        "partition": "queue",
        "evidence": "journal",
        "summary": "One queued job.",
        "initial": ["queued"],
        "terminal": ["done"],
        "settles_before_close": True,
        "states": {"queued": "", "running": "", "done": ""},
        "facts": {"result": "str?"},
        "required": {},
        "allowed": {"result": ["ok", "error", "timeout"]},
        "meanings": {"result": {"ok": "", "error": "", "timeout": ""}},
        "groups": {"result": {"success": ["ok"], "failure": ["error", "timeout"]}},
        "transitions": [{"from": "queued", "to": ["running"]}, {"from": "running", "to": ["done"]}],
        "edges": {"queued": ["running"], "running": ["done"]},
    } | changes


def spec(*invariants: dict[str, Any]) -> Spec:
    return Spec.model_validate(
        {
            "format": "repo2ree-behaviour-spec/1",
            "digest": "d",
            "vocabulary_digest": "v",
            "components": {"api": {"name": "api", "process": "api", "summary": ""}},
            "entities": {"Job": job()},
            "boundaries": {},
            "invariants": list(invariants),
        }
    )


def rule(when: dict[str, Any], require: dict[str, Any] | None = None, rule_id: str = "r") -> dict[str, Any]:
    return {"id": rule_id, "pattern": "requires", "summary": "", "when": when, "require": require}


def stated(value: object) -> str:
    return condition("result", CONDITION.validate_python(value), GROUPS)


def test_a_value_list_that_is_whole_groups_reads_as_those_groups() -> None:
    assert stated({"in": ["error", "timeout"]}) == "result ∈ failure"
    assert stated({"in": ["timeout", "ok", "error"]}) == "result ∈ success ∪ failure"  # noqa: RUF001
    assert stated({"in": ["ok", "error"]}) == "result ∈ {ok, error}"


def test_other_conditions_read_as_written() -> None:
    assert stated({"not": "ok"}) == "result ≠ ok"
    assert stated({"per": "mode", "in": {"fast": ["ok"], "slow": ["ok", ""]}}) == (
        'result by the trigger\'s mode (fast: ok; slow: ok, "")'
    )
    assert stated(False) == "result = false"
    assert stated("ok") == "result = ok"


def test_each_kind_of_rule_reads_as_a_sentence() -> None:
    entity = {"kind": "entity", "entity": "Job", "from": ["queued"], "to": ["running"], "where": {}}
    cases = {
        "eventually done": None,
        "result ∈ failure": {"kind": "guard", "where": {"result": {"in": ["error", "timeout"]}}},
        "no Job in running with the same queue": {"kind": "exclusion", "entity": "Job", "in_states": ["running"]},
        "Job keyed by its own key reached done, before it": {
            "kind": "entity",
            "entity": "Job",
            "key_from": "$key",
            "reached": ["done"],
            "order": "before",
        },
        "jobs.accepted keyed by job_id was recorded": {
            "kind": "message",
            "boundary": "jobs",
            "message": "accepted",
            "key_from": "job_id",
        },
    }
    for expected, require in cases.items():
        invariant = Invariant.model_validate(rule(entity, require) | {"eventually": ["done"]})
        assert trigger_text(spec(), invariant) == "Job from queued → running"
        assert requirement_text(spec(), invariant) == expected

    message = Invariant.model_validate(
        rule({"kind": "message", "boundary": "jobs", "message": "accepted", "where": {"result": "ok"}})
    )
    assert trigger_text(spec(), message) == "jobs.accepted where result = ok"


def test_rules_are_listed_under_the_values_they_name_and_otherwise_under_every_value() -> None:
    named, every = rule_values(
        spec(
            rule({"kind": "entity", "entity": "Job", "to": ["done"], "where": {"result": {"not": "ok"}}}, None, "a"),
            rule({"kind": "entity", "entity": "Job", "to": ["done"]}, None, "b"),
        )
    )

    assert named == {("Job", "result", "error"): ["a"], ("Job", "result", "timeout"): ["a"]}
    assert every == {"Job": ["machine:Job", "b"]}
