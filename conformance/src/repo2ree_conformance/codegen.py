"""Render the vocabulary as the JSON Schema owners emit against (``contracts/behaviour/events.schema.json``).

Only the vocabulary is published; the rules stay with the checker, and nothing the
product runs is generated from the specification.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from repo2ree_conformance.spec import BoundarySpec, EntitySpec, FactType, Spec

SCHEMA_ID = "urn:repo2ree:contracts:behaviour:events"
MESSAGE_KINDS = ("send", "receive", "abandon")
FACT_SCHEMA: dict[str, dict[str, Any]] = {
    "str": {"type": "string"},
    "str?": {"type": ["string", "null"]},
    "bool": {"type": "boolean"},
    "bool?": {"type": ["boolean", "null"]},
    "int": {"type": "integer"},
    "int?": {"type": ["integer", "null"]},
}
NON_NULL = {"str": "string", "bool": "boolean", "int": "integer"}


def _facts(declared: dict[str, FactType], required: Iterable[str] = ()) -> dict[str, Any]:
    """Declared facts by type, open to the owner's own; required ones present and not null."""
    names = sorted(required)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            name: FACT_SCHEMA[kind] if name not in names else {"type": NON_NULL[kind.rstrip("?")]}
            for name, kind in sorted(declared.items())
        },
    }
    if names:
        schema["required"] = names
    return schema


def _envelope(kind: dict[str, Any], subject: str, owner: str, required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "kind": kind,
            "subject": {"const": subject},
            "owner": {"const": owner},
            "key": {"type": "string"},
            "partition": {"type": ["string", "null"]},
        },
        "required": ["kind", "subject", "owner", "key", *required],
    }


def _entity(name: str, entity: EntitySpec) -> dict[str, Any]:
    branch = _envelope({"const": "transition"}, name, entity.owner, ["to"])
    states = list(entity.states)
    branch["properties"] |= {"from": {"enum": [None, *states]}, "to": {"enum": states}, "facts": _facts(entity.facts)}
    by_facts: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for state, facts in sorted(entity.required.items()):
        by_facts[tuple(sorted(facts))].append(state)
    branch["allOf"] = [
        {
            "if": {"properties": {"to": {"enum": targets}}},
            "then": {"properties": {"facts": _facts(entity.facts, facts)}, "required": ["facts"]},
        }
        for facts, targets in sorted(by_facts.items())
    ]
    if not branch["allOf"]:
        del branch["allOf"]
    branch["description"] = f"{entity.summary} Evidence: {entity.evidence}."
    return branch


def _boundary(name: str, boundary: BoundarySpec) -> dict[str, Any]:
    def message(kind: str, names: list[str]) -> dict[str, Any]:
        branch = _envelope({"const": kind}, name, boundary.sender, ["message"])
        branch["properties"]["message"] = {"enum": names}
        branch["allOf"] = [
            {
                "if": {"properties": {"message": {"const": item}}},
                "then": {
                    "properties": {"facts": _facts(boundary.facts.get(item, {}), boundary.required.get(item, ()))},
                    **({"required": ["facts"]} if boundary.required.get(item) else {}),
                },
            }
            for item in names
        ]
        return branch

    abandon = _envelope({"const": "abandon"}, name, boundary.sender, [])
    abandon["properties"] |= {
        "message": {"type": "null"},
        "facts": {"type": "object", "properties": {"reason": {"type": "string"}}},
    }
    return {
        "description": boundary.summary,
        "oneOf": [message("send", [boundary.request]), message("receive", list(boundary.responses)), abandon],
    }


def render_schema(spec: Spec) -> str:
    """The journal record contract as JSON Schema: the vocabulary, open to what owners add beyond it."""
    declared = sorted({*spec.entities, *spec.boundaries})
    processes = sorted({component.process for component in spec.components.values()})
    opened: dict[str, Any] = {
        "type": "object",
        "properties": {
            "kind": {"const": "journal.opened"},
            "process": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
            "epoch": {"type": "integer", "minimum": 1},
            "hosts": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "vocabulary": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        },
        "required": ["kind", "process", "epoch", "hosts", "vocabulary"],
        # A journal speaks for every component its process hosts, and only for them.
        "allOf": [
            {
                "if": {"properties": {"process": {"const": process}}},
                "then": {"properties": {"hosts": {"const": sorted(spec.hosted_by(process))}}},
            }
            for process in processes
        ],
    }
    closed = {
        "type": "object",
        "properties": {"kind": {"const": "journal.closed"}, "final": {"const": True}},
        "required": ["kind"],
    }
    undeclared = {
        "description": "A subject the vocabulary does not declare: the owner's own, never judged.",
        "type": "object",
        "properties": {
            "kind": {"enum": ["transition", *MESSAGE_KINDS]},
            "subject": {"type": "string", "not": {"enum": declared}},
            "owner": {"type": "string"},
            "key": {"type": "string"},
            "facts": {"type": "object"},
        },
        "required": ["kind", "subject", "owner", "key"],
    }
    defs: dict[str, Any] = {"journal.opened": opened, "journal.closed": closed, "undeclared": undeclared}
    defs |= {name: _entity(name, entity) for name, entity in sorted(spec.entities.items())}
    defs |= {name: _boundary(name, boundary) for name, boundary in sorted(spec.boundaries.items())}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "repo2ree behaviour journal record",
        "description": (
            "One line of a behaviour journal. Generated from specifications/behaviour/vocabulary by "
            "`python -m repo2ree_conformance generate`; do not edit. Sequence, epochs, and the header are "
            "checked per journal by `python -m repo2ree_conformance validate-journal`."
        ),
        "x-vocabulary": spec.vocabulary_digest,
        "type": "object",
        "properties": {"v": {"const": 1}, "seq": {"type": "integer", "minimum": 1}, "at": {"type": "string"}},
        "required": ["v", "seq", "kind"],
        "oneOf": [{"$ref": f"#/$defs/{name}"} for name in defs],
        "$defs": defs,
    }
    return json.dumps(schema, indent=2) + "\n"
