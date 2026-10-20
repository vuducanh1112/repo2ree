"""The behaviour specification: entities, boundaries, and invariants, validated as a whole."""

from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

type FactType = Literal["str", "str?", "bool", "bool?", "int", "int?"]
type Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
type Condition = dict[str, JsonValue]

# The only fact a requirement may name that is not a declared fact: the trigger's own key.
OWN_KEY = "$key"
# The source state of an entity's first transition, where a trigger may name it.
CREATED = "(none)"


class SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @staticmethod
    def one_or_many(value: object) -> object:
        """A single name where a list is expected means a list of one."""
        return (value,) if isinstance(value, str) else value


class Component(SpecModel):
    name: Name
    process: Name
    summary: str


class Transition(SpecModel):
    source: Name = Field(alias="from")
    targets: tuple[Name, ...] = Field(alias="to", min_length=1)
    why: str = ""

    @field_validator("targets", mode="before")
    @classmethod
    def _targets(cls, value: object) -> object:
        return cls.one_or_many(value)


class EntitySpec(SpecModel):
    """One state machine with a single owning component."""

    def settles_at(self, closed: bool, final: bool) -> bool:
        """Whether an instance still open when its owner's journal ended this way is left unsettled."""
        if not closed:
            return False
        return self.settles_before_close is True or (self.settles_before_close == "final" and final)

    name: Name
    owner: Name
    key: Name
    partition: Name
    evidence: Literal["journal", "git"]
    initial: tuple[Name, ...] = Field(min_length=1)
    terminal: tuple[Name, ...] = ()
    # True: terminal whenever its owner's journal closes. "final": it may outlive a restart, but must
    # be terminal when its owner closes the journal for good. False: no close settles it.
    settles_before_close: bool | Literal["final"]
    summary: str
    states: dict[Name, str]
    facts: dict[Name, FactType] = {}
    transitions: tuple[Transition, ...]

    @field_validator("initial", mode="before")
    @classmethod
    def _initial(cls, value: object) -> object:
        return cls.one_or_many(value)

    @property
    def edges(self) -> dict[str, frozenset[str]]:
        merged: dict[str, set[str]] = defaultdict(set)
        for transition in self.transitions:
            merged[transition.source].update(transition.targets)
        return {state: frozenset(merged.get(state, ())) for state in self.states}

    def allows(self, source: str | None, target: str) -> bool:
        if source is None:
            return target in self.initial
        return target in self.edges.get(source, frozenset())

    @model_validator(mode="after")
    def coherent_machine(self) -> Self:
        states = set(self.states)
        unknown = ({*self.initial, *self.terminal} | {t.source for t in self.transitions}) - states
        unknown |= {target for t in self.transitions for target in t.targets} - states
        if unknown:
            raise ValueError(f"{self.name}: unknown states {sorted(unknown)}")
        pairs = [(t.source, target) for t in self.transitions for target in t.targets]
        if len(pairs) != len(set(pairs)):
            raise ValueError(f"{self.name}: a transition is declared twice")
        if leaving := {source for source, _ in pairs} & set(self.terminal):
            raise ValueError(f"{self.name}: terminal states have transitions: {sorted(leaving)}")
        reachable, frontier = set(self.initial), list(self.initial)
        while frontier:
            for target in self.edges[frontier.pop()]:
                if target not in reachable:
                    reachable.add(target)
                    frontier.append(target)
        if unreachable := states - reachable:
            raise ValueError(f"{self.name}: unreachable states {sorted(unreachable)}")
        if self.settles_before_close and not self.terminal:
            raise ValueError(f"{self.name}: an entity that settles needs a terminal state")
        if self.key in self.facts:
            raise ValueError(f"{self.name}: the key {self.key!r} is the identity, not a fact")
        return self


class CitedEntity(SpecModel):
    """An entity's record for the boundary's key, at the transition into ``reached``; ``fact`` is its identity."""

    entity: Name
    reached: Name
    fact: Name


class CitedMessage(SpecModel):
    """A message of the exchange; its identity is the journal reference of its record."""

    message: Name


class CitingEntity(CitedEntity):
    """An entity's record whose ``fact`` names the cited record."""


class CitingMessage(SpecModel):
    """A message whose ``fact`` names the cited record."""

    message: Name
    fact: Name


class Citation(SpecModel):
    """One record naming another, which it could only know once the other existed: evidence of order."""

    by: CitingEntity | CitingMessage
    cited: CitedEntity | CitedMessage

    @model_validator(mode="after")
    def across_the_boundary(self) -> Self:
        if isinstance(self.by, CitingEntity) == isinstance(self.cited, CitedEntity):
            raise ValueError("a citation links one of the exchange's messages and one entity record")
        return self

    @property
    def record(self) -> CitedEntity:
        """The entity side of the citation, citing or cited."""
        if isinstance(self.by, CitingEntity):
            return self.by
        if isinstance(self.cited, CitedEntity):
            return self.cited
        raise ValueError("a citation without an entity side")  # Refused by the validator above.

    @property
    def message(self) -> str:
        """The exchange side of the citation, citing or cited."""
        if isinstance(self.by, CitingMessage):
            return self.by.message
        if isinstance(self.cited, CitedMessage):
            return self.cited.message
        raise ValueError("a citation without a message side")  # Refused by the validator above.


class BoundarySpec(SpecModel):
    """One request/response exchange between two components, recorded by the sender."""

    name: Name
    sender: Name
    receiver: Name
    key: Name
    partition: Name
    summary: str
    request: Name
    responses: tuple[Name, ...] = Field(min_length=1)
    messages: dict[Name, str]
    facts: dict[Name, dict[Name, FactType]] = {}
    # Records of the exchange and of an entity keyed like it that name each other:
    # the only way the checker orders evidence across sources.
    cites: tuple[Citation, ...] = ()

    @model_validator(mode="after")
    def coherent_boundary(self) -> Self:
        declared = {self.request, *self.responses}
        if missing := declared - set(self.messages):
            raise ValueError(f"{self.name}: undescribed messages {sorted(missing)}")
        if extra := set(self.messages) - declared:
            raise ValueError(f"{self.name}: messages outside the exchange {sorted(extra)}")
        if self.request in self.responses:
            raise ValueError(f"{self.name}: the request cannot also be a response")
        if unknown := set(self.facts) - declared:
            raise ValueError(f"{self.name}: facts for unknown messages {sorted(unknown)}")
        for citation in self.cites:
            for side in (citation.by, citation.cited):
                if isinstance(side, CitedMessage | CitingMessage) and side.message not in declared:
                    raise ValueError(f"{self.name}: cites unknown message {side.message!r}")
            if isinstance(citation.by, CitingMessage) and citation.by.fact not in self.facts.get(
                citation.by.message, {}
            ):
                raise ValueError(
                    f"{self.name}: {citation.by.message} cites through undeclared fact {citation.by.fact!r}"
                )
        return self


class EntityTrigger(SpecModel):
    entity: Name
    to: tuple[Name, ...] = Field(min_length=1)
    source: tuple[str, ...] = Field(default=(), alias="from")
    where: Condition = {}

    @field_validator("to", "source", mode="before")
    @classmethod
    def _states(cls, value: object) -> object:
        return cls.one_or_many(value)


class MessageTrigger(SpecModel):
    boundary: Name
    message: Name
    where: Condition = {}


class EntityRequirement(SpecModel):
    """The keyed entity reached one of the states (with facts), optionally before the trigger."""

    entity: Name
    key_from: str
    reached: tuple[Name, ...] = Field(min_length=1)
    where: Condition = {}
    order: Literal["any", "before"] = "any"

    @field_validator("reached", mode="before")
    @classmethod
    def _reached(cls, value: object) -> object:
        return (value,) if isinstance(value, str) else value


class MessageRequirement(SpecModel):
    boundary: Name
    message: Name
    key_from: str
    order: Literal["any", "before"] = "any"


class GuardRequirement(SpecModel):
    """The triggering transition's own facts satisfy a condition."""

    where: Condition = Field(min_length=1)


class ExclusionRequirement(SpecModel):
    """No instance of the entity in the trigger's partition is in these states at the trigger."""

    entity: Name
    in_states: tuple[Name, ...] = Field(min_length=1)


type Requirement = EntityRequirement | MessageRequirement | GuardRequirement | ExclusionRequirement


class Invariant(SpecModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]
    pattern: Literal["requires", "response", "guard", "excludes"]
    summary: str
    when: EntityTrigger | MessageTrigger
    require: Requirement | None = None
    eventually: tuple[Name, ...] = ()

    @model_validator(mode="after")
    def pattern_fields(self) -> Self:
        expected: dict[str, tuple[type, ...]] = {
            "requires": (EntityRequirement, MessageRequirement),
            "guard": (GuardRequirement,),
            "excludes": (ExclusionRequirement,),
            "response": (type(None),),
        }
        if not isinstance(self.require, expected[self.pattern]):
            raise ValueError(f"{self.id}: '{self.pattern}' does not take this 'require'")
        if (self.pattern == "response") != bool(self.eventually):
            raise ValueError(f"{self.id}: only 'response' takes 'eventually'")
        if self.pattern in {"response", "guard", "excludes"} and not isinstance(self.when, EntityTrigger):
            raise ValueError(f"{self.id}: '{self.pattern}' takes an entity trigger")
        return self


class Spec(SpecModel):
    components: dict[Name, Component]
    entities: dict[Name, EntitySpec]
    boundaries: dict[Name, BoundarySpec]
    invariants: tuple[Invariant, ...]

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json", by_alias=True), sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(canonical.encode()).hexdigest()

    def trigger_facts(self, trigger: EntityTrigger | MessageTrigger) -> dict[str, FactType]:
        if isinstance(trigger, EntityTrigger):
            return dict(self.entities[trigger.entity].facts)
        return dict(self.boundaries[trigger.boundary].facts.get(trigger.message, {}))

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
        return self

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
        conditions = dict(when.where)
        if isinstance(invariant.require, GuardRequirement):
            conditions.update(invariant.require.where)
        if unknown := set(conditions) - set(trigger_facts):
            raise ValueError(f"{invariant.id}: 'where' names undeclared facts {sorted(unknown)}")
        for condition in conditions.values():
            check_condition(invariant.id, condition)
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
            for condition in require.where.values():
                check_condition(invariant.id, condition)
            partition = entity_target.partition
        else:
            boundary = self.boundaries.get(require.boundary)
            if boundary is None or require.message not in boundary.messages:
                raise ValueError(f"{invariant.id}: unknown requirement {require.boundary}.{require.message}")
            partition = boundary.partition
        if partition != self.trigger_partition(when):
            raise ValueError(f"{invariant.id}: trigger and requirement are partitioned differently")


def check_condition(owner: str, condition: JsonValue) -> None:
    if isinstance(condition, dict):
        if len(condition) != 1 or next(iter(condition)) not in {"not", "in"}:
            raise ValueError(f"{owner}: a condition is a value, {{not = value}}, or {{in = [values]}}")
        if "in" in condition and not isinstance(condition["in"], list):
            raise ValueError(f"{owner}: 'in' takes a list")
    elif isinstance(condition, list):
        raise ValueError(f"{owner}: use {{in = [values]}} for alternatives")


def matches(where: Condition, facts: dict[str, JsonValue]) -> bool:
    """Absent facts never satisfy a condition, including a negated one; a fact recorded as null is absent."""
    for name, condition in where.items():
        if facts.get(name) is None:
            return False
        value = facts[name]
        if isinstance(condition, dict):
            if "not" in condition and value == condition["not"]:
                return False
            options = condition.get("in")
            if isinstance(options, list) and value not in options:
                return False
        elif value != condition:
            return False
    return True


def fact_problem(declared: dict[str, FactType], facts: dict[str, Any]) -> str | None:
    """Why a fact set disagrees with its declaration, or None."""
    if unknown := set(facts) - set(declared):
        return f"undeclared facts {sorted(unknown)}"
    for name, value in facts.items():
        kind = declared[name]
        if value is None:
            if not kind.endswith("?"):
                return f"fact {name!r} is null"
            continue
        expected = {"str": str, "bool": bool, "int": int}[kind.rstrip("?")]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            return f"fact {name!r} is not {kind}"
    return None


def parse_spec(
    entities: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    invariants: dict[str, Any],
    components: dict[str, Any],
) -> Spec:
    """Build the specification from already-parsed TOML documents."""
    component_specs = [Component.model_validate(item) for item in components.get("component", [])]
    if unexpected := set(components) - {"component"}:
        raise ValueError(f"components file has unexpected tables {sorted(unexpected)}")
    if len({component.name for component in component_specs}) != len(component_specs):
        raise ValueError("component names must be unique")
    entity_specs = [EntitySpec.model_validate(document) for document in entities]
    boundary_specs = [BoundarySpec.model_validate(document) for document in boundaries]
    if len({entity.name for entity in entity_specs}) != len(entity_specs):
        raise ValueError("entity names must be unique")
    if len({boundary.name for boundary in boundary_specs}) != len(boundary_specs):
        raise ValueError("boundary names must be unique")
    if unexpected := set(invariants) - {"invariant"}:
        raise ValueError(f"invariants file has unexpected tables {sorted(unexpected)}")
    return Spec(
        components={component.name: component for component in component_specs},
        entities={entity.name: entity for entity in entity_specs},
        boundaries={boundary.name: boundary for boundary in boundary_specs},
        invariants=tuple(Invariant.model_validate(item) for item in invariants.get("invariant", [])),
    )
