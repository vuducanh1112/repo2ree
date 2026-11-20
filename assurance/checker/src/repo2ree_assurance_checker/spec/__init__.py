"""The behaviour specification: entities, boundaries, and invariants, validated as a whole.

It has two layers. The vocabulary (``vocabulary/*.toml``, with ``components.toml``) is
the contract owners emit against: each subject's owner, key, states or messages, and
facts with their types and where they are required; and the catalogue of the operations
core runs. The rules (``entities/*.toml``,
``boundaries/*.toml``, ``invariants.toml``) are what the checker holds the evidence to.
Aggregate machines (``aggregates/*.toml``) follow every part of a document an entity
commits; a move no edge allows violates the aggregate's rule. Document rules (``documents/*.toml``)
read one commit of that document at a time, with the files it holds. Only the vocabulary is published to the product
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
    ITEM,
    KEYED,
    STANDINGS,
    TREE_FORMAT,
    WILDCARD,
    AggregateSpec,
    BasisPair,
    DocumentPath,
    Edge,
    FieldMachine,
    Lifecycle,
    MachineKind,
    Placed,
    ReceiptMachine,
    SubMachine,
    TreeEntry,
    field_of,
    place,
)
from repo2ree_assurance_checker.spec.base import CREATED, OWN_KEY, Condition, FactType, Name, SpecModel
from repo2ree_assurance_checker.spec.documents import (
    AgreesPair,
    CanonicalPair,
    DigestKind,
    DocumentRule,
    DocumentRules,
    FilePair,
    PathsPair,
    ReferencePair,
    VerdictPolicy,
)
from repo2ree_assurance_checker.spec.facts import absent, declared_facts, fact_problems, matches
from repo2ree_assurance_checker.spec.invariants import (
    EachRequirement,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    FactGroups,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    MessageTrigger,
    NextRequirement,
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
    Catalogue,
    Component,
    EntityVocabulary,
    FactDeclaration,
    FactEntry,
    allowed_values,
    fact_types,
    parse_vocabulary,
    with_catalogue,
)


class Spec(SpecModel):
    components: dict[Name, Component]
    entities: dict[Name, EntitySpec]
    boundaries: dict[Name, BoundarySpec]
    invariants: tuple[Invariant, ...]
    aggregates: dict[Name, AggregateSpec] = Field(default_factory=dict)
    documents: dict[Name, DocumentRules] = Field(default_factory=dict)
    operations: dict[Name, str] = Field(default_factory=dict)
    review_operations: dict[Name, str] = Field(default_factory=dict)

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
            "operations": dumped["operations"],
            "review_operations": dumped["review_operations"],
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
        for name, rules in self.documents.items():
            judged = self.aggregates.get(rules.aggregate)
            if judged is None:
                raise ValueError(f"document rules for {name}, of {rules.aggregate}, which is no aggregate")
            standing = [rule.id for rule in rules.rules if rule.pattern == "standing"]
            unread = [receipt for receipt, machine in judged.receipts.items() if machine.basis is None]
            if standing and unread:
                raise ValueError(f"{standing[0]}: receipts {unread} of {name} have no basis to stand on")
        return self

    def _check_aggregate(self, aggregate: AggregateSpec) -> None:
        """An aggregate watches a document its entity commits, in that entity's states and receipt kinds."""
        entity = self.entities.get(aggregate.name)
        if entity is None or entity.evidence != "git":
            raise ValueError(f"aggregate {aggregate.name}: not an entity whose evidence is its committed document")
        if unknown := set(aggregate.lifecycle.states) - set(entity.states):
            raise ValueError(f"aggregate {aggregate.name}: lifecycle names unknown states {sorted(unknown)}")
        if aggregate.receipt_entity is None:
            if aggregate.receipts:
                raise ValueError(f"aggregate {aggregate.name}: has receipts, but names no entity whose they are")
            return
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
        if isinstance(require, NextRequirement):
            following = self.entities.get(require.entity)
            if following is None or not set(require.reached) <= set(following.states):
                raise ValueError(f"{invariant.id}: unknown requirement {require.entity}.{'/'.join(require.reached)}")
            if unknown := set(require.where) - set(following.facts):
                raise ValueError(f"{invariant.id}: requirement 'where' names undeclared facts {sorted(unknown)}")
            for fact, condition in require.where.items():
                check_condition(invariant.id, fact, condition, following.allowed, trigger_allowed, trigger_facts)
            if following.partition != self.trigger_partition(when):
                raise ValueError(f"{invariant.id}: trigger and requirement are partitioned differently")
        if isinstance(require, EachRequirement):
            named = self.entities.get(require.entity)
            if named is None or not set(require.reached) <= set(named.states):
                raise ValueError(f"{invariant.id}: unknown requirement {require.entity}.{'/'.join(require.reached)}")
            if require.fact not in named.facts:
                raise ValueError(f"{invariant.id}: {require.entity} has no fact {require.fact!r}")
            if trigger_facts.get(require.of) != "[str]":
                raise ValueError(f"{invariant.id}: 'of' names {require.of!r}, which is not a list fact of the trigger")
            if named.partition != self.trigger_partition(when):
                raise ValueError(f"{invariant.id}: trigger and requirement are partitioned differently")
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


def _spelled_out(
    word: EntityVocabulary | BoundaryVocabulary | Catalogue, catalogue: Catalogue | None
) -> EntityVocabulary | BoundaryVocabulary | Catalogue:
    if isinstance(word, EntityVocabulary):
        return word.model_copy(
            update={"facts": {name: with_catalogue(entry, catalogue) for name, entry in word.facts.items()}}
        )
    if isinstance(word, BoundaryVocabulary):
        facts = {
            message: {name: with_catalogue(entry, catalogue) for name, entry in declared.items()}
            for message, declared in word.facts.items()
        }
        return word.model_copy(update={"facts": facts})
    return word


def _named_operations(aggregate: AggregateSpec) -> set[str]:
    taken = {operation for machine in aggregate.machines for edge in machine.edges for operation in edge.by}
    return taken | {aggregate.created_by, aggregate.restored_by, *aggregate.writes_nothing, *aggregate.signed_by}


def operation_problems(spec: Spec) -> list[str]:
    """Where the specification names operations the catalogue does not, or leaves one of an REE's unsaid.

    Every operation an aggregate names is catalogued and none is a review's but in an aggregate that reviews
    another, and each of an REE's operations is named by an aggregate: what it may change, or that it writes
    nothing. A specification without a catalogue, as older revisions are, has nothing to hold them to.
    """
    if not spec.operations:
        return []
    catalogued = {*spec.operations, *spec.review_operations}
    problems: list[str] = []
    named: set[str] = set()
    for aggregate in spec.aggregates.values():
        own = _named_operations(aggregate)
        if unknown := own - catalogued:
            problems.append(f"{aggregate.name} names operations the catalogue does not: {sorted(unknown)}")
        if aggregate.reviews is None and (reviews := own & set(spec.review_operations)):
            problems.append(f"{aggregate.name} names review operations, which change no REE: {sorted(reviews)}")
        named |= own
    if spec.aggregates and (unsaid := set(spec.operations) - named):
        problems.append(f"operations no aggregate says what they may change: {sorted(unsaid)}")
    return problems


def parse_spec(
    vocabulary: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    invariants: dict[str, Any],
    components: dict[str, Any],
    aggregates: Sequence[dict[str, Any]] = (),
    documents: Sequence[dict[str, Any]] = (),
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
    catalogues = [word for word in words if isinstance(word, Catalogue)]
    if len(catalogues) > 1:
        raise ValueError(f"one operation catalogue, not {[catalogue.name for catalogue in catalogues]}")
    catalogue = catalogues[0] if catalogues else None
    words = [_spelled_out(word, catalogue) for word in words]
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
    document_specs = [DocumentRules.model_validate(document) for document in documents]
    if len({rules.name for rules in document_specs}) != len(document_specs):
        raise ValueError("one file of document rules per aggregate, and one per review of it")
    return Spec(
        components={component.name: component for component in component_specs},
        entities={entity.name: entity for entity in entity_specs},
        boundaries={boundary.name: boundary for boundary in boundary_specs},
        invariants=tuple(
            Invariant.model_validate(spell_out_groups(item, groups)) for item in invariants.get("invariant", [])
        ),
        aggregates={aggregate.name: aggregate for aggregate in aggregate_specs},
        documents={rules.name: rules for rules in document_specs},
        operations=catalogues[0].operations if catalogues else {},
        review_operations=catalogues[0].review_operations if catalogues else {},
    )


__all__ = [
    "CREATED",
    "FIELD_STATES",
    "ITEM",
    "KEYED",
    "OWN_KEY",
    "STANDINGS",
    "TREE_FORMAT",
    "WILDCARD",
    "AggregateSpec",
    "AgreesPair",
    "BasisPair",
    "BoundarySpec",
    "BoundaryVocabulary",
    "CanonicalPair",
    "Catalogue",
    "Citation",
    "CitedEntity",
    "CitedMessage",
    "CitingEntity",
    "CitingMessage",
    "Component",
    "Condition",
    "DigestKind",
    "DocumentPath",
    "DocumentRule",
    "DocumentRules",
    "EachRequirement",
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
    "FilePair",
    "GuardRequirement",
    "Invariant",
    "Lifecycle",
    "MachineKind",
    "MachineRules",
    "MessageRequirement",
    "MessageTrigger",
    "Name",
    "NextRequirement",
    "PathsPair",
    "Placed",
    "ReceiptMachine",
    "ReferencePair",
    "Requirement",
    "Spec",
    "SpecModel",
    "SubMachine",
    "Transition",
    "TreeEntry",
    "VerdictPolicy",
    "absent",
    "allowed_values",
    "check_condition",
    "declared_facts",
    "fact_problems",
    "fact_types",
    "field_of",
    "matches",
    "operation_problems",
    "parse_spec",
    "parse_vocabulary",
    "place",
    "spell_out_groups",
]
