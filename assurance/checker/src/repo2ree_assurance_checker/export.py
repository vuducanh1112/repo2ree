"""The specification as data: what views read and compare instead of importing the checker.

Everything the checker holds the evidence to, as the specification's own files name it
(``from`` and ``to``), with what a reader would otherwise have to derive: each machine's
merged ``edges``, each aggregate's spelled-out ``machines``, the digests, and a ``kind``
on every part that takes one of several shapes (a trigger, a requirement, a citation's
side). ``format`` changes when a field does, so a reader can refuse a document it does
not know.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from repo2ree_assurance_checker.spec import (
    CitedEntity,
    CitedMessage,
    CitingEntity,
    CitingMessage,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    MessageRequirement,
    MessageTrigger,
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
    CitingEntity: "entity",
    CitedEntity: "entity",
    CitingMessage: "message",
    CitedMessage: "message",
}


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


def _tagged(model: BaseModel) -> dict[str, Any]:
    return {"kind": KINDS[type(model)], **_dump(model)}


def export_spec(spec: Spec) -> dict[str, Any]:
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
    return {
        "format": FORMAT,
        "digest": spec.digest,
        "vocabulary_digest": spec.vocabulary_digest,
        "components": {name: _dump(component) for name, component in spec.components.items()},
        "entities": entities,
        "boundaries": boundaries,
        "invariants": invariants,
        "aggregates": aggregates,
    }
