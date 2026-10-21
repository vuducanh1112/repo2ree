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
    EntitySpec,
    EntityTrigger,
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
    assert set(spec.entities) == {"Allocation", "Attempt", "AuthorApiAction", "Ree", "Receipt"}
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
    docs.machine("AuthorApiAction")["transitions"].append({"from": "succeeded", "to": ["requested"]})
    with pytest.raises(ValidationError, match="terminal states have transitions"):
        docs.parse()


def test_the_vocabulary_digest_changes_with_the_contract_but_not_with_the_rules() -> None:
    docs = documents()
    spec = docs.parse()
    docs.invariants["invariant"] = docs.invariants["invariant"][1:]
    docs.machine("AuthorApiAction")["transitions"] = docs.machine("AuthorApiAction")["transitions"][:-1]
    rules_changed = docs.parse()
    assert rules_changed.digest != spec.digest
    assert rules_changed.vocabulary_digest == spec.vocabulary_digest
    docs.words("AuthorApiAction")["facts"]["queue"] = "str?"
    assert docs.parse().vocabulary_digest != spec.vocabulary_digest


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda docs: docs.machine("AuthorApiAction").update(initial="paused"), "unknown states"),
        (
            lambda docs: docs.machine("AuthorApiAction")["transitions"].append(
                {"from": "requested", "to": ["running"]}
            ),
            "twice",
        ),
        (lambda docs: docs.words("AuthorApiAction")["states"].update(orphan="Never entered."), "unreachable states"),
        (lambda docs: docs.words("AuthorApiAction")["facts"].update(action_id="str"), "is the identity"),
        (lambda docs: docs.words("AuthorApiAction")["facts"].update(path="float"), "facts"),
        (
            lambda docs: docs.words("AuthorApiAction")["facts"].update(path={"type": "str", "required_in": ["done"]}),
            "facts required in unknown states",
        ),
        (
            lambda docs: docs.words("AuthorApiAction")["facts"].update(
                path={"type": "str", "required": True, "required_in": ["requested"]}
            ),
            "either required everywhere or required_in",
        ),
        (lambda docs: docs.machine("AuthorApiAction").update(states={"requested": "x"}), "Extra inputs"),
        (lambda docs: docs.words("AuthorApiAction").update(initial="requested"), "Extra inputs"),
        (lambda docs: docs.vocabulary.remove(docs.words("AuthorApiAction")), "machines without a vocabulary"),
    ],
)
def test_incoherent_machines_are_rejected(mutate: Any, message: str) -> None:
    docs = documents()
    mutate(docs)
    with pytest.raises((ValidationError, ValueError), match=message):
        docs.parse()


def test_an_entity_without_a_machine_is_unconstrained() -> None:
    docs = documents()
    docs.entities.remove(docs.machine("AuthorApiAction"))
    action = docs.parse().entities["AuthorApiAction"]
    assert not action.constrained
    assert set(action.initial) == set(action.states)
    assert (action.terminal, action.settles_before_close, action.transitions) == ((), False, ())
    assert action.allows(None, "succeeded")
    assert action.allows("succeeded", "requested")
    assert not action.allows("requested", "sealed")


def rule(docs: Documents, rule_id: str) -> dict[str, Any]:
    return next(invariant for invariant in docs.invariants["invariant"] if invariant["id"] == rule_id)


def producers(docs: Documents) -> dict[str, Any]:
    operation: dict[str, Any] = rule(docs, "receipts-come-from-their-producers")["require"]["where"]["operation"]
    return operation


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda docs: rule(docs, "dispatch-success-is-captured")["require"]["where"].update(outcome="succeded"),
            r"outcome names values its declaration does not list: \['succeded'\]",
        ),
        (
            lambda docs: rule(docs, "api-success-is-recorded")["when"].update(where={"action": "build_runtim"}),
            r"action names values its declaration does not list",
        ),
        (lambda docs: producers(docs)["in"].pop("experiment"), r"missing \['experiment'\]"),
        (lambda docs: producers(docs)["in"].update(painting=["build_runtime"]), r"unlisted \['painting'\]"),
        (
            lambda docs: producers(docs)["in"]["runtime"].append("build_runtim"),
            r"operation for kind runtime names values its declaration does not list",
        ),
        (lambda docs: producers(docs).update(per="outcome"), "'per' names 'outcome', which is not a trigger fact"),
    ],
)
def test_rules_name_only_values_the_vocabulary_lists(mutate: Any, message: str) -> None:
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
DERIVED = {"required", "allowed", "meanings", "groups", "constrained"}


def test_a_revision_with_vocabulary_and_rules_in_one_file_still_reads() -> None:
    """``diff --base`` reads specifications committed before the vocabulary had files of its own."""
    spec = load_spec()

    def combined_words(entity: EntitySpec) -> dict[str, Any]:
        """The entity as one old-style file: its facts keep the values they list, as such files did."""
        dumped = entity.model_dump(mode="json", by_alias=True, exclude=DERIVED)
        for fact in entity.allowed:
            dumped["facts"][fact] = {"type": dumped["facts"][fact], "values": dict(entity.meanings[fact])}
        return dumped

    combined = [combined_words(spec.entities[name]) for name in sorted(spec.entities)]
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
        ({"when": {"entity": "AuthorApiAction", "to": "finished"}}, "unknown trigger"),
        ({"when": {"entity": "AuthorApiAction", "to": "succeeded", "where": {"colour": "red"}}}, "undeclared facts"),
        ({"require": {"entity": "Attempt", "key_from": "outcome", "reached": "captured"}}, "not a trigger fact"),
        ({"require": {"entity": "Attempt", "key_from": "attempt_id", "reached": "done"}}, "unknown requirement"),
        ({"pattern": "response"}, "'response' does not take this 'require'"),
        ({"pattern": "guard"}, "'guard' does not take this 'require'"),
        (
            {"require": {"entity": "Receipt", "in_states": ["stale"]}, "pattern": "excludes"},
            "'excludes' takes an entity",
        ),
        (
            {"when": {"entity": "AuthorApiAction", "to": "succeeded", "where": {"path": ["a", "b"]}}},
            "in = \\[values\\]",
        ),
    ],
)
def test_incoherent_invariants_are_rejected(change: dict[str, Any], message: str) -> None:
    docs = documents()
    recorded = next(item for item in docs.invariants["invariant"] if item["id"] == "api-success-is-recorded")
    recorded.update(change)
    if change.get("pattern") == "excludes":
        recorded["when"] = {"boundary": "dispatch", "message": "result"}
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
            {
                "by": {"entity": "AuthorApiAction", "reached": "requested", "fact": "path"},
                "cited": {"message": "exec_action"},
            },
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
    trigger = rules["api-success-is-recorded"].when
    assert isinstance(trigger, EntityTrigger)
    condition = trigger.where["action"]
    assert isinstance(condition, dict)
    assert isinstance(condition["in"], list)
    on_the_ree = set(condition["in"])
    assert on_the_ree == set().union(
        *(groups[name] for name in ("source", "editing", "assistance", "evidence", "lifecycle"))
    )
