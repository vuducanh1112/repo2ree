"""The specification is validated as a whole, and the runtime module is generated from it."""

from __future__ import annotations

import copy
import tomllib
from typing import Any

import pytest
from pydantic import ValidationError

from repo2ree_conformance.codegen import render_machines
from repo2ree_conformance.files import GENERATED_MACHINES, SPEC_DIR, load_spec
from repo2ree_conformance.spec import fact_problem, matches, parse_spec


def documents() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    def read(subdirectory: str) -> list[dict[str, Any]]:
        return [tomllib.loads(path.read_text()) for path in sorted((SPEC_DIR / subdirectory).glob("*.toml"))]

    return (
        read("entities"),
        read("boundaries"),
        tomllib.loads((SPEC_DIR / "invariants.toml").read_text()),
        tomllib.loads((SPEC_DIR / "components.toml").read_text()),
    )


def entity(entities: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(document for document in entities if document["name"] == name)


def test_the_checked_in_specification_is_valid() -> None:
    spec = load_spec()
    assert set(spec.entities) == {"Allocation", "Attempt", "Ree", "Run", "Step"}
    assert spec.hosted_by("api") == {"api", "supervisor"}
    assert set(spec.boundaries) == {"dispatch"}
    assert spec.digest.startswith("sha256:")


def test_the_generated_runtime_module_matches_the_specification() -> None:
    assert GENERATED_MACHINES.read_text() == render_machines(load_spec()), (
        "run `python -m repo2ree_conformance generate`"
    )


def test_the_digest_changes_with_behaviour_but_not_with_file_order() -> None:
    entities, boundaries, invariants, components = documents()
    digest = parse_spec(entities, boundaries, invariants, components).digest
    assert parse_spec(list(reversed(entities)), boundaries, invariants, components).digest == digest
    changed = copy.deepcopy(entities)
    entity(changed, "Run")["transitions"].append({"from": "succeeded", "to": ["queued"]})
    with pytest.raises(ValidationError, match="terminal states have transitions"):
        parse_spec(changed, boundaries, invariants, components)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda run: run.update(initial="paused"), "unknown states"),
        (lambda run: run["transitions"].append({"from": "queued", "to": ["running"]}), "declared twice"),
        (lambda run: run["states"].update(orphan="Never entered."), "unreachable states"),
        (lambda run: run["facts"].update(run_id="str"), "is the identity"),
        (lambda run: run["facts"].update(operation="float"), "facts"),
    ],
)
def test_incoherent_machines_are_rejected(mutate: Any, message: str) -> None:
    entities, boundaries, invariants, components = documents()
    mutate(entity(entities, "Run"))
    with pytest.raises(ValidationError, match=message):
        parse_spec(entities, boundaries, invariants, components)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"when": {"entity": "Run", "to": "finished"}}, "unknown trigger"),
        ({"when": {"entity": "Run", "to": "succeeded", "where": {"colour": "red"}}}, "undeclared facts"),
        ({"require": {"entity": "Attempt", "key_from": "run_id", "reached": "captured"}}, "not a trigger fact"),
        ({"require": {"entity": "Attempt", "key_from": "attempt_id", "reached": "done"}}, "unknown requirement"),
        ({"pattern": "response"}, "'response' does not take this 'require'"),
        ({"pattern": "guard"}, "'guard' does not take this 'require'"),
        ({"require": {"entity": "Step", "in_states": ["stale"]}, "pattern": "excludes"}, "'excludes' takes an entity"),
        ({"when": {"entity": "Run", "to": "succeeded", "where": {"operation": ["a", "b"]}}}, "in = \\[values\\]"),
    ],
)
def test_incoherent_invariants_are_rejected(change: dict[str, Any], message: str) -> None:
    entities, boundaries, invariants, components = documents()
    run_success = next(item for item in invariants["invariant"] if item["id"] == "run-success-is-backed")
    run_success.update(change)
    if change.get("pattern") == "excludes":
        run_success["when"] = {"boundary": "dispatch", "message": "result"}
    with pytest.raises(ValidationError, match=message):
        parse_spec(entities, boundaries, invariants, components)


def test_owners_and_boundary_ends_must_be_declared_components() -> None:
    entities, boundaries, invariants, components = documents()
    components["component"] = [item for item in components["component"] if item["name"] != "core"]
    with pytest.raises(ValidationError, match="owner 'core' is not a declared component"):
        parse_spec(entities, boundaries, invariants, components)


@pytest.mark.parametrize(
    ("citation", "problem"),
    [
        (
            {"by": {"entity": "Run", "reached": "queued", "fact": "operation"}, "cited": {"message": "exec_action"}},
            "not keyed by attempt_id",
        ),
        (
            {"by": {"entity": "Attempt", "reached": "gone", "fact": "operation"}, "cited": {"message": "exec_action"}},
            "unknown state 'gone'",
        ),
        (
            {"by": {"entity": "Attempt", "reached": "pending", "fact": "nope"}, "cited": {"message": "exec_action"}},
            "undeclared fact 'nope'",
        ),
        (
            {
                "by": {"message": "result", "fact": "nope"},
                "cited": {"entity": "Attempt", "reached": "captured", "fact": "commit"},
            },
            "undeclared fact 'nope'",
        ),
        (
            {"by": {"message": "result", "fact": "status"}, "cited": {"message": "exec_action"}},
            "one of the exchange's messages and one entity record",
        ),
    ],
)
def test_citations_link_a_message_and_a_record_keyed_like_the_exchange(citation: dict[str, Any], problem: str) -> None:
    entities, boundaries, invariants, components = documents()
    boundaries[0]["cites"] = [citation]
    with pytest.raises(ValidationError, match=problem):
        parse_spec(entities, boundaries, invariants, components)


def test_conditions_never_match_absent_facts() -> None:
    assert matches({"operation": {"not": "provision"}}, {"operation": "build"})
    assert not matches({"operation": {"not": "provision"}}, {})
    assert matches({"status": {"in": ["a", "b"]}}, {"status": "b"})
    assert not matches({"status": "a"}, {"status": "b"})


def test_fact_types_are_checked() -> None:
    declared: dict[str, Any] = {"name": "str", "count": "int?", "flag": "bool"}
    assert fact_problem(declared, {"name": "x", "count": None, "flag": True}) is None
    assert fact_problem(declared, {"flag": 1}) == "fact 'flag' is not bool"
    assert fact_problem(declared, {"count": True}) == "fact 'count' is not int?"
    assert fact_problem(declared, {"name": None}) == "fact 'name' is null"
    assert fact_problem(declared, {"other": 1}) == "undeclared facts ['other']"
