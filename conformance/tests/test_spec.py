"""The specification is validated as a whole, and the published contract is generated from it."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from repo2ree_conformance.codegen import render_schema
from repo2ree_conformance.files import GENERATED_SCHEMA, SPEC_DIR, load_spec, split_combined
from repo2ree_conformance.spec import (
    GuardRequirement,
    Spec,
    fact_problems,
    matches,
    parse_spec,
    spell_out_groups,
)


@dataclass
class Documents:
    """The specification's TOML documents, parsed but not yet validated, for tests to change."""

    vocabulary: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    boundaries: list[dict[str, Any]]
    invariants: dict[str, Any]
    components: dict[str, Any]

    def words(self, name: str) -> dict[str, Any]:
        return next(document for document in self.vocabulary if document["name"] == name)

    def machine(self, name: str) -> dict[str, Any]:
        return next(document for document in self.entities if document["name"] == name)

    def parse(self) -> Spec:
        return parse_spec(self.vocabulary, self.entities, self.boundaries, self.invariants, self.components)


def documents() -> Documents:
    def read(subdirectory: str) -> list[dict[str, Any]]:
        return [tomllib.loads(path.read_text()) for path in sorted((SPEC_DIR / subdirectory).glob("*.toml"))]

    return Documents(
        read("vocabulary"),
        read("entities"),
        read("boundaries"),
        tomllib.loads((SPEC_DIR / "invariants.toml").read_text()),
        tomllib.loads((SPEC_DIR / "components.toml").read_text()),
    )


def test_the_checked_in_specification_is_valid() -> None:
    spec = load_spec()
    assert set(spec.entities) == {"Allocation", "Attempt", "AuthorApiAction", "Ree", "Run", "Step"}
    assert spec.hosted_by("api") == {"api", "supervisor"}
    assert set(spec.boundaries) == {"dispatch"}
    assert spec.digest.startswith("sha256:")
    assert spec.vocabulary_digest.startswith("sha256:")
    assert spec.entities["Attempt"].required == {"completed": ("outcome",), "captured": ("commit", "changed")}
    assert spec.entities["Ree"].required == {"draft": ("cause",), "sealed": ("cause",)}
    assert spec.boundaries["dispatch"].required == {"result": ("status",)}


def test_the_published_contract_matches_the_vocabulary() -> None:
    assert GENERATED_SCHEMA.read_text() == render_schema(load_spec()), "run `python -m repo2ree_conformance generate`"


def test_the_digest_changes_with_behaviour_but_not_with_file_order() -> None:
    docs = documents()
    digest = docs.parse().digest
    docs.entities.reverse()
    docs.vocabulary.reverse()
    assert docs.parse().digest == digest
    docs.machine("Run")["transitions"].append({"from": "succeeded", "to": ["queued"]})
    with pytest.raises(ValidationError, match="terminal states have transitions"):
        docs.parse()


def test_the_vocabulary_digest_changes_with_the_contract_but_not_with_the_rules() -> None:
    docs = documents()
    spec = docs.parse()
    docs.invariants["invariant"] = docs.invariants["invariant"][1:]
    docs.machine("Run")["transitions"] = docs.machine("Run")["transitions"][:-1]
    rules_changed = docs.parse()
    assert rules_changed.digest != spec.digest
    assert rules_changed.vocabulary_digest == spec.vocabulary_digest
    docs.words("Run")["facts"]["queue"] = "str?"
    assert docs.parse().vocabulary_digest != spec.vocabulary_digest


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda docs: docs.machine("Run").update(initial="paused"), "unknown states"),
        (lambda docs: docs.machine("Run")["transitions"].append({"from": "queued", "to": ["running"]}), "twice"),
        (lambda docs: docs.words("Run")["states"].update(orphan="Never entered."), "unreachable states"),
        (lambda docs: docs.words("Run")["facts"].update(run_id="str"), "is the identity"),
        (lambda docs: docs.words("Run")["facts"].update(operation="float"), "facts"),
        (
            lambda docs: docs.words("Run")["facts"].update(operation={"type": "str", "required_in": ["done"]}),
            "facts required in unknown states",
        ),
        (
            lambda docs: docs.words("Run")["facts"].update(
                operation={"type": "str", "required": True, "required_in": ["queued"]}
            ),
            "either required everywhere or required_in",
        ),
        (lambda docs: docs.machine("Run").update(states={"queued": "x"}), "Extra inputs"),
        (lambda docs: docs.words("Run").update(initial="queued"), "Extra inputs"),
        (lambda docs: docs.entities.remove(docs.machine("Run")), "both a vocabulary and a machine"),
    ],
)
def test_incoherent_machines_are_rejected(mutate: Any, message: str) -> None:
    docs = documents()
    mutate(docs)
    with pytest.raises((ValidationError, ValueError), match=message):
        docs.parse()


def test_boundary_facts_are_required_on_every_record_of_their_message() -> None:
    docs = documents()
    docs.words("dispatch")["facts"]["result"]["status"] = {"type": "str", "required_in": ["result"]}
    with pytest.raises(ValidationError, match="use required = true"):
        docs.parse()


# Fields the specification derives from fact declarations, which an old combined file never carried.
DERIVED = {"required", "allowed", "meanings", "groups"}


def test_a_revision_with_vocabulary_and_rules_in_one_file_still_reads() -> None:
    """``diff --base`` reads specifications committed before the vocabulary had files of its own."""
    spec = load_spec()
    combined = [
        {**spec.entities[name].model_dump(mode="json", by_alias=True, exclude=DERIVED)}
        for name in sorted(spec.entities)
    ]
    exchanges = [
        {**boundary.model_dump(mode="json", by_alias=True, exclude=DERIVED)} for boundary in spec.boundaries.values()
    ]
    docs = documents()
    vocabulary, entities, boundaries = split_combined(combined, exchanges)
    # The rules as loaded, with group conditions already spelled out: the dumped words keep no groups.
    rules = [invariant.model_dump(mode="json", by_alias=True, exclude_none=True) for invariant in spec.invariants]
    invariants = {"invariant": rules}
    old = parse_spec(vocabulary, entities, boundaries, invariants, docs.components)
    assert {name: entity.edges for name, entity in old.entities.items()} == {
        name: entity.edges for name, entity in spec.entities.items()
    }
    assert old.boundaries["dispatch"].cites == spec.boundaries["dispatch"].cites


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
    docs = documents()
    run_success = next(item for item in docs.invariants["invariant"] if item["id"] == "run-success-is-backed")
    run_success.update(change)
    if change.get("pattern") == "excludes":
        run_success["when"] = {"boundary": "dispatch", "message": "result"}
    with pytest.raises(ValidationError, match=message):
        docs.parse()


def test_owners_and_boundary_ends_must_be_declared_components() -> None:
    docs = documents()
    docs.components["component"] = [item for item in docs.components["component"] if item["name"] != "core"]
    with pytest.raises(ValidationError, match="owner 'core' is not a declared component"):
        docs.parse()


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
    docs = documents()
    docs.boundaries[0]["cites"] = [citation]
    with pytest.raises(ValidationError, match=problem):
        docs.parse()


def test_conditions_never_match_absent_facts() -> None:
    assert matches({"operation": {"not": "provision"}}, {"operation": "build"})
    assert not matches({"operation": {"not": "provision"}}, {})
    assert matches({"status": {"in": ["a", "b"]}}, {"status": "b"})
    assert not matches({"status": "a"}, {"status": "b"})


def test_declared_facts_are_typed_required_ones_present_and_the_rest_the_owners_own() -> None:
    declared: dict[str, Any] = {"name": "str", "count": "int?", "flag": "bool"}
    assert fact_problems(declared, (), {"name": "x", "count": None, "flag": True}) == []
    assert fact_problems(declared, (), {"flag": 1}) == [("violated", "fact 'flag' is not bool")]
    assert fact_problems(declared, (), {"count": True}) == [("violated", "fact 'count' is not int?")]
    assert fact_problems(declared, (), {"name": None}) == [("violated", "fact 'name' is null")]
    assert fact_problems(declared, (), {"other": 1}) == []
    assert fact_problems(declared, ("name", "count"), {"count": None}) == [
        ("inconclusive", "missing required facts ['count', 'name']")
    ]


def test_a_fact_that_lists_its_values_takes_no_other() -> None:
    allowed = {"action": ("write_file", "seal_ree")}
    assert fact_problems({"action": "str"}, (), {"action": "seal_ree"}, allowed) == []
    assert fact_problems({"action": "str"}, (), {"action": "seal"}, allowed) == [
        ("violated", "fact 'action' is 'seal', which its declaration does not list")
    ]
    assert load_spec().entities["AuthorApiAction"].allowed["action"][:2] == ("create_ree", "release_workbench")


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ({"type": "str", "values": {"a": ""}, "groups": {"g": {"b": ""}}}, "lists its values or groups them"),
        ({"type": "int", "values": {"a": ""}}, "only a str fact lists its values"),
        ({"type": "str", "groups": {"g": {"a": ""}, "h": {"a": ""}}}, "a value belongs to one group"),
    ],
)
def test_incoherent_value_lists_are_rejected(declaration: dict[str, Any], message: str) -> None:
    docs = documents()
    docs.words("AuthorApiAction")["facts"]["action"] = declaration
    with pytest.raises(ValidationError, match=message):
        docs.parse()


def test_a_group_condition_is_spelled_out_as_the_groups_values() -> None:
    groups = {"AuthorApiAction": {"action": {"editing": ("write_file", "delete_file"), "reading": ("read_file",)}}}
    invariant = {
        "id": "x",
        "when": {
            "entity": "AuthorApiAction",
            "to": "succeeded",
            "where": {"action": {"group": ["editing", "reading"]}},
        },
        "require": {"where": {"action": {"group": "reading"}}},
    }
    spelled = spell_out_groups(invariant, groups)
    assert spelled["when"]["where"] == {"action": {"in": ["write_file", "delete_file", "read_file"]}}
    assert spelled["require"]["where"] == {"action": {"in": ["read_file"]}}
    with pytest.raises(ValueError, match="declares no groups"):
        spell_out_groups(invariant | {"require": {"where": {"action": {"group": "painting"}}}}, groups)


def test_the_author_rules_name_the_action_groups_they_mean() -> None:
    spec = load_spec()
    rules = {invariant.id: invariant for invariant in spec.invariants}
    declared = documents().words("AuthorApiAction")["facts"]["action"]["groups"]
    groups = {name: set(values) for name, values in declared.items()}
    guard = rules["only-long-actions-run"].require
    assert isinstance(guard, GuardRequirement)
    condition = guard.where["action"]
    assert isinstance(condition, dict)
    assert isinstance(condition["in"], list)
    long_running = set(condition["in"])
    assert long_running == groups["workbench"] | groups["source"] | groups["evidence"] | groups["lifecycle"]
