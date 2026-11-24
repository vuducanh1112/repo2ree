from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict

from repo2ree_assurance_checker.spec import (
    EachRequirement,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    MessageTrigger,
    NextRequirement,
    Spec,
)

CLI_CORE = frozenset({"core", "environment"})


class Scope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    components: tuple[str, ...]
    entities: tuple[str, ...]
    boundaries: tuple[str, ...]
    rules: tuple[str, ...]


def _named(invariant: Invariant) -> Iterator[tuple[bool, str]]:
    match invariant.when:
        case EntityTrigger(entity=entity):
            yield True, entity
        case MessageTrigger(boundary=boundary):
            yield False, boundary
    match invariant.require:
        case (
            EntityRequirement(entity=entity)
            | ExclusionRequirement(entity=entity)
            | NextRequirement(entity=entity)
            | EachRequirement(entity=entity)
        ):
            yield True, entity
        case MessageRequirement(boundary=boundary):
            yield False, boundary
        case GuardRequirement() | None:
            pass


def cli_core(spec: Spec) -> Scope:
    entities = tuple(sorted(name for name, entity in spec.entities.items() if entity.owner in CLI_CORE))
    boundaries = tuple(
        sorted(name for name, found in spec.boundaries.items() if {found.sender, found.receiver} <= CLI_CORE)
    )
    invariants = [
        invariant.id
        for invariant in spec.invariants
        if all(name in (entities if entity else boundaries) for entity, name in _named(invariant))
    ]
    rules = (
        "evidence",
        *(f"machine:{name}" for name in entities),
        *(f"boundary:{name}" for name in boundaries),
        *invariants,
        *(f"aggregate:{name}" for name in sorted(spec.aggregates) if name in entities),
        *(
            f"document:{rule.id}"
            for document in spec.documents.values()
            if document.aggregate in entities
            for rule in document.rules
        ),
    )
    return Scope(components=tuple(sorted(CLI_CORE)), entities=entities, boundaries=boundaries, rules=rules)
