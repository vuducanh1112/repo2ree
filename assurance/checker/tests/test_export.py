"""The exported specification says what the checker's model says, in plain data."""

from __future__ import annotations

import json
import typing

from repo2ree_assurance_checker import load_spec
from repo2ree_assurance_checker.export import FORMAT, KINDS, export_spec
from repo2ree_assurance_checker.spec import Citation, Invariant


def shapes(annotation: object) -> set[object]:
    """The classes a field may hold, through unions and ``type`` aliases."""
    if isinstance(annotation, typing.TypeAliasType):
        return shapes(annotation.__value__)
    members = typing.get_args(annotation)
    if not members:
        return set() if annotation is type(None) else {annotation}
    return {shape for member in members for shape in shapes(member)}


def test_every_shape_a_part_can_take_has_a_kind() -> None:
    fields = [Invariant.model_fields["when"], Invariant.model_fields["require"]]
    fields += [Citation.model_fields["by"], Citation.model_fields["cited"]]
    found = {shape for field in fields for shape in shapes(field.annotation)}
    assert found == set(KINDS)


def test_the_export_carries_the_model() -> None:
    spec = load_spec()
    document = json.loads(json.dumps(export_spec(spec)))

    assert document["format"] == FORMAT
    assert document["digest"] == spec.digest
    assert document["vocabulary_digest"] == spec.vocabulary_digest
    assert [rule["id"] for rule in document["invariants"]] == [rule.id for rule in spec.invariants]
    for name, entity in spec.entities.items():
        exported = document["entities"][name]
        assert {state: set(targets) for state, targets in exported["edges"].items()} == entity.edges
        assert [(t["from"], tuple(t["to"])) for t in exported["transitions"]] == [
            (t.source, t.targets) for t in entity.transitions
        ]
    for exported, invariant in zip(document["invariants"], spec.invariants, strict=True):
        assert exported["when"]["kind"] == KINDS[type(invariant.when)]
        assert (exported["require"] or {}).get("kind") == (invariant.require and KINDS[type(invariant.require)])
