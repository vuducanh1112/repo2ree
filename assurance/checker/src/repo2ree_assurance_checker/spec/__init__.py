"""The behaviour specification: entities, boundaries, and invariants, validated as a whole.

It has two layers. The vocabulary (``vocabulary/*.toml``, with ``components.toml``) is
the contract owners emit against: each subject's owner, key, states or messages, and
facts with their types and where they are required. The rules (``entities/*.toml``,
``boundaries/*.toml``, ``invariants.toml``) are what the checker holds the evidence to.
Aggregate machines (``aggregates/*.toml``) follow every part of a document an entity
commits; they are reported, not gated. Only the vocabulary is published to the product
(``contracts/behaviour``).

The package keeps each part apart: ``base`` (what they share), ``vocabulary`` (what owners
emit), ``rules`` (machines and exchanges), ``invariants`` (rules across entities), ``facts``
(recorded facts against all of them), and ``aggregates`` (the parts of a committed
document). ``Spec`` puts them together and checks that they agree.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from hashlib import sha256
from typing import Any, Self

from pydantic import Field, model_validator

from repo2ree_assurance_checker.spec.aggregates import (
    FIELD_STATES,
    KEYED,
    STANDINGS,
    AggregateSpec,
    Edge,
    FieldMachine,
    Lifecycle,
    MachineKind,
    ReceiptMachine,
    SubMachine,
)
from repo2ree_assurance_checker.spec.base import CREATED, OWN_KEY, Condition, FactType, Name, SpecModel
from repo2ree_assurance_checker.spec.facts import absent, declared_facts, fact_problems, matches
from repo2ree_assurance_checker.spec.invariants import (
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    FactGroups,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    MessageTrigger,
    Requirement,
    check_condition,
    spell_out_groups,
)
from repo2ree_assurance_checker.spec.rules import (
    BoundarySpec,
    Citation,
    CitedEntity,
    CitedMessage,
    CitingEntity,
    CitingMessage,
    EntitySpec,
    ExchangeRules,
    MachineRules,
    Transition,
)
from repo2ree_assurance_checker.spec.vocabulary import (
    BoundaryVocabulary,
    Component,
    EntityVocabulary,
    FactDeclaration,
    FactEntry,
    allowed_values,
    fact_types,
    parse_vocabulary,
)


class Spec(SpecModel):
    components: dict[Name, Component]
    entities: dict[Name, EntitySpec]
    boundaries: dict[Name, BoundarySpec]
    invariants: tuple[Invariant, ...]
    aggregates: dict[Name, AggregateSpec] = Field(default_factory=dict)

    @property
    def digest(self) -> str:
        return _digest(self.model_dump(mode="json", by_alias=True))

    @property
    def vocabulary(self) -> dict[str, Any]:
        """The contract owners emit against, without the rules: what ``contracts/behaviour`` publishes."""
        entity_fields = (
            *("owner", "key", "partition", "evidence", "summary", "states"),
            *("facts", "required", "allowed", "meanings", "groups"),
        )
        boundary_fields = (
            *("sender", "receiver", "key", "partition", "summary", "request", "responses", "messages"),
            *("facts", "required", "allowed"),
        )
        dumped = self.model_dump(mode="json")
        return {
            "components": dumped["components"],
            "entities": {
                name: {field: entity[field] for field in entity_fields} for name, entity in dumped["entities"].items()
            },
            "boundaries": {
                name: {field: boundary[field] for field in boundary_fields}
                for name, boundary in dumped["boundaries"].items()
            },
        }

    @property
    def vocabulary_digest(self) -> str:
        """Changes with the contract only: rules can change without touching what owners emit."""
        return _digest(self.vocabulary)

    def trigger_facts(self, trigger: EntityTrigger | MessageTrigger) -> dict[str, FactType]:
        if isinstance(trigger, EntityTrigger):
            return dict(self.entities[trigger.entity].facts)
        return dict(self.boundaries[trigger.boundary].facts.get(trigger.message, {}))

    def trigger_allowed(self, trigger: EntityTrigger | MessageTrigger) -> dict[str, tuple[str, ...]]:
        """The values the trigger's facts may take, for the facts that list them."""
        if isinstance(trigger, EntityTrigger):
            return dict(self.entities[trigger.entity].allowed)
        return dict(self.boundaries[trigger.boundary].allowed.get(trigger.message, {}))

    def trigger_partition(self, trigger: EntityTrigger | MessageTrigger) -> str:
        if isinstance(trigger, EntityTrigger):
            return self.entities[trigger.entity].partition
        return self.boundaries[trigger.boundary].partition

    def hosted_by(self, process: str) -> frozenset[str]:
        return frozenset(name for name, component in self.components.items() if component.process == process)

    @model_validator(mode="after")
    def coherent_references(self) -> Self:
        for name, entity in self.entities.items():
            if name != entity.name:
                raise ValueError(f"entity {entity.name!r} is filed as {name!r}")
            if entity.owner not in self.components:
                raise ValueError(f"{name}: owner {entity.owner!r} is not a declared component")
        for name, boundary in self.boundaries.items():
            if name != boundary.name:
                raise ValueError(f"boundary {boundary.name!r} is filed as {name!r}")
            if unknown := {boundary.sender, boundary.receiver} - set(self.components):
                raise ValueError(f"{name}: undeclared components {sorted(unknown)}")
            for citation in boundary.cites:
                side = citation.record
                target = self.entities.get(side.entity)
                if target is None or target.key != boundary.key:
                    raise ValueError(f"{name}: cites {side.entity!r}, which is not keyed by {boundary.key}")
                if side.reached not in target.states:
                    raise ValueError(f"{name}: cites {side.entity} reaching unknown state {side.reached!r}")
                if side.fact not in target.facts:
                    raise ValueError(f"{name}: cites {side.entity} through undeclared fact {side.fact!r}")
        if len({invariant.id for invariant in self.invariants}) != len(self.invariants):
            raise ValueError("invariant ids must be unique")
        for invariant in self.invariants:
            self._check_invariant(invariant)
        for aggregate in self.aggregates.values():
            self._check_aggregate(aggregate)
        return self

    def _check_aggregate(self, aggregate: AggregateSpec) -> None:
        """An aggregate watches a document its entity commits, in that entity's states and receipt kinds."""
        entity = self.entities.get(aggregate.name)
        if entity is None or entity.evidence != "git":
            raise ValueError(f"aggregate {aggregate.name}: not an entity whose evidence is its committed document")
        if unknown := set(aggregate.lifecycle.states) - set(entity.states):
            raise ValueError(f"aggregate {aggregate.name}: lifecycle names unknown states {sorted(unknown)}")
        receipts = self.entities.get(aggregate.receipt_entity)
        if receipts is None or receipts.partition != entity.key:
            raise ValueError(f"aggregate {aggregate.name}: {aggregate.receipt_entity} is not partitioned by it")
        if set(receipts.allowed.get("kind", ())) != set(aggregate.receipts):
            raise ValueError(
                f"aggregate {aggregate.name}: receipts {sorted(aggregate.receipts)} are not the kinds "
                f"{aggregate.receipt_entity} lists {sorted(receipts.allowed.get('kind', ()))}"
            )
        if unknown := set(STANDINGS) ^ set(receipts.states):
            raise ValueError(
                f"aggregate {aggregate.name}: receipt standings differ from its entity's: {sorted(unknown)}"
            )

    def _check_invariant(self, invariant: Invariant) -> None:
        when = invariant.when
        if isinstance(when, EntityTrigger):
            entity = self.entities.get(when.entity)
            if entity is None or not set(when.to) <= set(entity.states):
                raise ValueError(f"{invariant.id}: unknown trigger {when.entity}.{list(when.to)}")
            if unknown := set(when.source) - set(entity.states) - {CREATED}:
                raise ValueError(f"{invariant.id}: unknown trigger source states {sorted(unknown)}")
            if unknown := set(invariant.eventually) - set(entity.states):
                raise ValueError(f"{invariant.id}: unknown 'eventually' states {sorted(unknown)}")
        else:
            boundary = self.boundaries.get(when.boundary)
            if boundary is None or when.message not in boundary.messages:
                raise ValueError(f"{invariant.id}: unknown trigger {when.boundary}.{when.message}")
        trigger_facts = self.trigger_facts(when)
        trigger_allowed = self.trigger_allowed(when)
        conditions = dict(when.where)
        if isinstance(invariant.require, GuardRequirement):
            conditions.update(invariant.require.where)
        if unknown := set(conditions) - set(trigger_facts):
            raise ValueError(f"{invariant.id}: 'where' names undeclared facts {sorted(unknown)}")
        for fact, condition in conditions.items():
            check_condition(invariant.id, fact, condition, trigger_allowed, trigger_allowed, trigger_facts)
        require = invariant.require
        if isinstance(require, ExclusionRequirement):
            target = self.entities.get(require.entity)
            if target is None or not set(require.in_states) <= set(target.states):
                raise ValueError(f"{invariant.id}: unknown exclusion {require.entity}.{list(require.in_states)}")
            if target.partition != self.trigger_partition(when):
                raise ValueError(f"{invariant.id}: trigger and exclusion are partitioned differently")
        if not isinstance(require, EntityRequirement | MessageRequirement):
            return
        if require.key_from != OWN_KEY and require.key_from not in trigger_facts:
            raise ValueError(f"{invariant.id}: key_from {require.key_from!r} is not a trigger fact")
        if isinstance(require, EntityRequirement):
            entity_target = self.entities.get(require.entity)
            if entity_target is None or not set(require.reached) <= set(entity_target.states):
                raise ValueError(f"{invariant.id}: unknown requirement {require.entity}.{'/'.join(require.reached)}")
            if unknown := set(require.where) - set(entity_target.facts):
                raise ValueError(f"{invariant.id}: requirement 'where' names undeclared facts {sorted(unknown)}")
            for fact, condition in require.where.items():
                check_condition(invariant.id, fact, condition, entity_target.allowed, trigger_allowed, trigger_facts)
            partition = entity_target.partition
        else:
            boundary = self.boundaries.get(require.boundary)
            if boundary is None or require.message not in boundary.messages:
                raise ValueError(f"{invariant.id}: unknown requirement {require.boundary}.{require.message}")
            partition = boundary.partition
        if partition != self.trigger_partition(when):
            raise ValueError(f"{invariant.id}: trigger and requirement are partitioned differently")


def _digest(document: object) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(canonical.encode()).hexdigest()


def _unconstrained(word: EntityVocabulary) -> dict[str, Any]:
    """The machine of an entity that has none: any state, any move, never settled."""
    return {"initial": tuple(word.states), "settles_before_close": False, "transitions": (), "constrained": False}


def parse_spec(
    vocabulary: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    invariants: dict[str, Any],
    components: dict[str, Any],
    aggregates: Sequence[dict[str, Any]] = (),
) -> Spec:
    """Build the specification from already-parsed TOML documents: the vocabulary, then the rules."""
    component_specs = [Component.model_validate(item) for item in components.get("component", [])]
    if unexpected := set(components) - {"component"}:
        raise ValueError(f"components file has unexpected tables {sorted(unexpected)}")
    if len({component.name for component in component_specs}) != len(component_specs):
        raise ValueError("component names must be unique")
    words = [parse_vocabulary(document) for document in vocabulary]
    if len({word.name for word in words}) != len(words):
        raise ValueError("vocabulary names must be unique")
    entity_words = {word.name: word for word in words if isinstance(word, EntityVocabulary)}
    boundary_words = {word.name: word for word in words if isinstance(word, BoundaryVocabulary)}
    machines = [MachineRules.model_validate(document) for document in entities]
    exchanges = [ExchangeRules.model_validate(document) for document in boundaries]
    if len({machine.name for machine in machines}) != len(machines):
        raise ValueError("entity names must be unique")
    if len({exchange.name for exchange in exchanges}) != len(exchanges):
        raise ValueError("boundary names must be unique")
    if unknown := {machine.name for machine in machines} - set(entity_words):
        raise ValueError(f"machines without a vocabulary: {sorted(unknown)}")
    if unknown := {exchange.name for exchange in exchanges} - set(boundary_words):
        raise ValueError(f"boundary rules without a vocabulary: {sorted(unknown)}")
    declared = {machine.name: dict(machine) for machine in machines}
    entity_specs = [
        EntitySpec.model_validate(word.entity_fields() | declared.get(name, _unconstrained(word)))
        for name, word in entity_words.items()
    ]
    rules = {exchange.name: exchange for exchange in exchanges}
    boundary_specs = [
        BoundarySpec.model_validate(word.boundary_fields() | {"cites": rules[name].cites if name in rules else ()})
        for name, word in boundary_words.items()
    ]
    if unexpected := set(invariants) - {"invariant"}:
        raise ValueError(f"invariants file has unexpected tables {sorted(unexpected)}")
    groups = {name: word.fact_groups() for name, word in entity_words.items()}
    aggregate_specs = [AggregateSpec.model_validate(document) for document in aggregates]
    if len({aggregate.name for aggregate in aggregate_specs}) != len(aggregate_specs):
        raise ValueError("aggregate names must be unique")
    return Spec(
        components={component.name: component for component in component_specs},
        entities={entity.name: entity for entity in entity_specs},
        boundaries={boundary.name: boundary for boundary in boundary_specs},
        invariants=tuple(
            Invariant.model_validate(spell_out_groups(item, groups)) for item in invariants.get("invariant", [])
        ),
        aggregates={aggregate.name: aggregate for aggregate in aggregate_specs},
    )


__all__ = [
    "CREATED",
    "FIELD_STATES",
    "KEYED",
    "OWN_KEY",
    "STANDINGS",
    "AggregateSpec",
    "BoundarySpec",
    "BoundaryVocabulary",
    "Citation",
    "CitedEntity",
    "CitedMessage",
    "CitingEntity",
    "CitingMessage",
    "Component",
    "Condition",
    "Edge",
    "EntityRequirement",
    "EntitySpec",
    "EntityTrigger",
    "EntityVocabulary",
    "ExchangeRules",
    "ExclusionRequirement",
    "FactDeclaration",
    "FactEntry",
    "FactGroups",
    "FactType",
    "FieldMachine",
    "GuardRequirement",
    "Invariant",
    "Lifecycle",
    "MachineKind",
    "MachineRules",
    "MessageRequirement",
    "MessageTrigger",
    "Name",
    "ReceiptMachine",
    "Requirement",
    "Spec",
    "SpecModel",
    "SubMachine",
    "Transition",
    "absent",
    "allowed_values",
    "check_condition",
    "declared_facts",
    "fact_problems",
    "fact_types",
    "matches",
    "parse_spec",
    "parse_vocabulary",
    "spell_out_groups",
]
