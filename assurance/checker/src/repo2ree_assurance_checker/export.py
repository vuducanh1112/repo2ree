from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from repo2ree_assurance_checker.files import Source
from repo2ree_assurance_checker.scope import cli_core
from repo2ree_assurance_checker.spec import (
    CitedEntity,
    CitedMessage,
    CitingEntity,
    CitingMessage,
    EachRequirement,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    MessageRequirement,
    MessageTrigger,
    NextRequirement,
    Spec,
)

FORMAT = "repo2ree-behaviour-spec/1"

KINDS: dict[type[BaseModel], str] = {
    EntityTrigger: "entity",
    MessageTrigger: "message",
    EntityRequirement: "entity",
    MessageRequirement: "message",
    GuardRequirement: "guard",
    ExclusionRequirement: "exclusion",
    NextRequirement: "next",
    EachRequirement: "each",
    CitingEntity: "entity",
    CitedEntity: "entity",
    CitingMessage: "message",
    CitedMessage: "message",
}


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


def _tagged(model: BaseModel) -> dict[str, Any]:
    return {"kind": KINDS[type(model)], **_dump(model)}


def export_spec(spec: Spec, sources: tuple[Source, ...]) -> dict[str, Any]:
    entities = {
        name: _dump(entity) | {"edges": {state: sorted(targets) for state, targets in entity.edges.items()}}
        for name, entity in spec.entities.items()
    }
    boundaries = {
        name: _dump(boundary)
        | {"cites": [{"by": _tagged(cite.by), "cited": _tagged(cite.cited)} for cite in boundary.cites]}
        for name, boundary in spec.boundaries.items()
    }
    invariants = [
        _dump(invariant)
        | {
            "when": _tagged(invariant.when),
            "require": None if invariant.require is None else _tagged(invariant.require),
        }
        for invariant in spec.invariants
    ]
    aggregates = {
        name: _dump(aggregate) | {"machines": [_dump(machine) for machine in aggregate.machines]}
        for name, aggregate in spec.aggregates.items()
    }
    documents = {
        name: {
            "aggregate": rules.aggregate,
            "document": rules.document,
            "rules": [_dump(rule) for rule in rules.rules],
        }
        for name, rules in spec.documents.items()
    }
    return {
        "format": FORMAT,
        "digest": spec.digest,
        "vocabulary_digest": spec.vocabulary_digest,
        "components": {name: _dump(component) for name, component in spec.components.items()},
        "entities": entities,
        "boundaries": boundaries,
        "invariants": invariants,
        "aggregates": aggregates,
        "documents": documents,
        "sources": [_dump(source) for source in sources],
        "cli_core": _dump(cli_core(spec)),
    }
