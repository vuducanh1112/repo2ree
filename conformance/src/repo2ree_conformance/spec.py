"""The behaviour specification: entities, boundaries, and invariants, validated as a whole.

It has two layers. The vocabulary (``vocabulary/*.toml``, with ``components.toml``) is
the contract owners emit against: each subject's owner, key, states or messages, and
facts with their types and where they are required. The rules (``entities/*.toml``,
``boundaries/*.toml``, ``invariants.toml``) are what the checker holds the evidence to.
Only the vocabulary is published to the product (``contracts/behaviour``).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
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


class FactDeclaration(SpecModel):
    """A fact with where it must be present; a bare type string declares an optional fact."""

    type: FactType
    # Present (and not null) on every transition of the entity, or on every record of the message.
    required: bool = False
    # Present (and not null) on every transition into these states; entities only.
    required_in: tuple[Name, ...] = ()
    # The only values the fact may take, each with what it means; or the same values, grouped.
    values: dict[Name, str] = {}
    groups: dict[Name, dict[Name, str]] = {}

    @field_validator("required_in", mode="before")
    @classmethod
    def _states(cls, value: object) -> object:
        return cls.one_or_many(value)

    @model_validator(mode="after")
    def one_requirement(self) -> Self:
        if self.required and self.required_in:
            raise ValueError("a fact is either required everywhere or required_in some states")
        return self

    @model_validator(mode="after")
    def coherent_values(self) -> Self:
        if self.values and self.groups:
            raise ValueError("a fact lists its values or groups them, not both")
        if self.allowed and self.type.rstrip("?") != "str":
            raise ValueError("only a str fact lists its values")
        grouped = [value for group in self.groups.values() for value in group]
        if len(grouped) != len(set(grouped)):
            raise ValueError("a value belongs to one group")
        return self

    @property
    def allowed(self) -> tuple[str, ...]:
        return tuple(self.meanings)

    @property
    def meanings(self) -> dict[str, str]:
        """Each listed value with what it means, in declaration order, whether listed or grouped."""
        return {**self.values, **{value: meaning for group in self.groups.values() for value, meaning in group.items()}}


type FactEntry = FactType | FactDeclaration


def fact_types(declared: dict[str, FactEntry]) -> dict[str, FactType]:
    return {name: entry if isinstance(entry, str) else entry.type for name, entry in declared.items()}


def allowed_values(declared: dict[str, FactEntry]) -> dict[str, tuple[str, ...]]:
    """The facts that list their values, with those values."""
    return {name: entry.allowed for name, entry in declared.items() if not isinstance(entry, str) and entry.allowed}


class Transition(SpecModel):
    source: Name = Field(alias="from")
    targets: tuple[Name, ...] = Field(alias="to", min_length=1)
    why: str = ""

    @field_validator("targets", mode="before")
    @classmethod
    def _targets(cls, value: object) -> object:
        return cls.one_or_many(value)


class EntitySpec(SpecModel):
    """One state machine with a single owning component.

    An entity without a machine (no ``entities/<name>.toml``) is unconstrained: it may
    start in and move between any of its states, never settles, and declares no edges
    for the evidence to cover. Its records are still checked: owner, facts, partition,
    and that each move starts where the previous one ended.
    """

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
    # The facts every transition into a state must carry, by state.
    required: dict[Name, tuple[Name, ...]] = {}
    # The only values a fact may take, for the facts that list them; what each means; and how they group.
    allowed: dict[Name, tuple[str, ...]] = {}
    meanings: dict[Name, dict[str, str]] = {}
    groups: dict[Name, dict[Name, tuple[str, ...]]] = {}
    transitions: tuple[Transition, ...]
    constrained: bool = True

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
        if not self.constrained:
            return target in self.states
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
        if not self.constrained and (self.transitions or self.terminal or set(self.initial) != states):
            raise ValueError(f"{self.name}: an unconstrained entity starts anywhere and declares no edges")
        if self.key in self.facts:
            raise ValueError(f"{self.name}: the key {self.key!r} is the identity, not a fact")
        if unknown := set(self.required) - states:
            raise ValueError(f"{self.name}: facts required in unknown states {sorted(unknown)}")
        if unknown := {fact for facts in self.required.values() for fact in facts} - set(self.facts):
            raise ValueError(f"{self.name}: requires undeclared facts {sorted(unknown)}")
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
    # The facts every record of a message must carry, by message.
    required: dict[Name, tuple[Name, ...]] = {}
    # The only values a fact may take, by message, for the facts that list them.
    allowed: dict[Name, dict[Name, tuple[str, ...]]] = {}
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
        for message, facts in self.required.items():
            if unknown := set(facts) - set(self.facts.get(message, {})):
                raise ValueError(f"{self.name}: {message} requires undeclared facts {sorted(unknown)}")
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


class EntityVocabulary(SpecModel):
    """The words owners emit for one entity: who records it, how it is keyed, its states and facts."""

    kind: Literal["entity"]
    name: Name
    owner: Name
    key: Name
    partition: Name
    evidence: Literal["journal", "git"]
    summary: str
    states: dict[Name, str]
    facts: dict[Name, FactEntry] = {}

    def fact_groups(self) -> dict[str, dict[str, tuple[str, ...]]]:
        """Each fact that groups its values, with the values of each group."""
        return {
            name: {group: tuple(values) for group, values in entry.groups.items()}
            for name, entry in self.facts.items()
            if not isinstance(entry, str) and entry.groups
        }

    def entity_fields(self) -> dict[str, Any]:
        required: dict[str, list[str]] = defaultdict(list)
        for fact, entry in self.facts.items():
            if isinstance(entry, str):
                continue
            for state in self.states if entry.required else entry.required_in:
                required[state].append(fact)
        fields = self.model_dump(exclude={"kind", "facts"})
        return fields | {
            "facts": fact_types(self.facts),
            "required": {s: tuple(f) for s, f in required.items()},
            "allowed": allowed_values(self.facts),
            "meanings": {
                name: entry.meanings
                for name, entry in self.facts.items()
                if not isinstance(entry, str) and entry.meanings
            },
            "groups": self.fact_groups(),
        }


class BoundaryVocabulary(SpecModel):
    """The words of one exchange: its ends, key, messages, and each message's facts."""

    kind: Literal["boundary"]
    name: Name
    sender: Name
    receiver: Name
    key: Name
    partition: Name
    summary: str
    request: Name
    responses: tuple[Name, ...] = Field(min_length=1)
    messages: dict[Name, str]
    facts: dict[Name, dict[Name, FactEntry]] = {}

    @model_validator(mode="after")
    def required_everywhere(self) -> Self:
        for message, facts in self.facts.items():
            if any(not isinstance(entry, str) and entry.required_in for entry in facts.values()):
                raise ValueError(f"{self.name}: {message} has no states; use required = true")
        return self

    def boundary_fields(self) -> dict[str, Any]:
        required = {
            message: tuple(name for name, entry in facts.items() if not isinstance(entry, str) and entry.required)
            for message, facts in self.facts.items()
        }
        fields = self.model_dump(exclude={"kind", "facts"})
        return fields | {
            "facts": {message: fact_types(facts) for message, facts in self.facts.items()},
            "required": {message: facts for message, facts in required.items() if facts},
            "allowed": {
                message: allowed for message, facts in self.facts.items() if (allowed := allowed_values(facts))
            },
        }


class MachineRules(SpecModel):
    """One entity's machine: where instances start, the edges they may take, and when they settle."""

    name: Name
    initial: tuple[Name, ...] = Field(min_length=1)
    terminal: tuple[Name, ...] = ()
    settles_before_close: bool | Literal["final"]
    transitions: tuple[Transition, ...]

    @field_validator("initial", mode="before")
    @classmethod
    def _initial(cls, value: object) -> object:
        return cls.one_or_many(value)


class ExchangeRules(SpecModel):
    """One boundary's rules beyond the exchange pattern itself: the records that name each other."""

    name: Name
    cites: tuple[Citation, ...] = ()


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


def check_condition(
    owner: str,
    fact: str,
    condition: JsonValue,
    listed: Mapping[str, tuple[str, ...]],
    trigger_listed: Mapping[str, tuple[str, ...]],
    trigger_facts: Collection[str],
) -> None:
    """A condition's shape, and each value it names against the values its fact lists, where the fact lists them.

    ``{per = fact, in = {value = [values]}}`` takes its alternatives from the trigger's
    ``fact``: it gives a list for each value that fact lists, so none is left unsaid.
    """
    values = listed.get(fact)

    def named(items: list[JsonValue], context: str = "") -> None:
        if values is not None and (unknown := [item for item in items if item not in values]):
            raise ValueError(f"{owner}: {fact}{context} names values its declaration does not list: {unknown}")

    if isinstance(condition, dict):
        if set(condition) == {"per", "in"}:
            by, table = condition["per"], condition["in"]
            if not isinstance(by, str) or by not in trigger_facts:
                raise ValueError(f"{owner}: 'per' names {by!r}, which is not a trigger fact")
            if not isinstance(table, dict) or not all(isinstance(items, list) for items in table.values()):
                raise ValueError(f"{owner}: with 'per', 'in' takes a list of values for each value of {by}")
            keys = trigger_listed.get(by)
            if keys is None:
                raise ValueError(f"{owner}: 'per' needs {by} to list its values")
            if set(table) != set(keys):
                missing, extra = sorted(set(keys) - set(table)), sorted(set(table) - set(keys))
                raise ValueError(
                    f"{owner}: 'in' must give a list for each value of {by}: missing {missing}, unlisted {extra}"
                )
            for key, items in table.items():
                named(items, f" for {by} {key}")  # type: ignore[arg-type]
            return
        if len(condition) != 1 or next(iter(condition)) not in {"not", "in"}:
            raise ValueError(
                f"{owner}: a condition is a value, {{not = value}}, {{in = [values]}}, {{group = ...}}, "
                "or {per = fact, in = {value = [values]}}"
            )
        if "in" in condition:
            if not isinstance(condition["in"], list):
                raise ValueError(f"{owner}: 'in' takes a list")
            named(condition["in"])
        else:
            named([condition["not"]])
    elif isinstance(condition, list):
        raise ValueError(f"{owner}: use {{in = [values]}} for alternatives")
    else:
        named([condition])


def matches(where: Condition, facts: dict[str, JsonValue], trigger: dict[str, JsonValue] | None = None) -> bool:
    """Absent facts never satisfy a condition, including a negated one; a fact recorded as null is absent.

    A ``{per, in}`` condition reads its key from ``trigger``'s facts: the trigger's, when the
    facts are another record's; the facts themselves otherwise.
    """
    for name, condition in where.items():
        if facts.get(name) is None:
            return False
        value = facts[name]
        if isinstance(condition, dict):
            if "per" in condition:
                key = (facts if trigger is None else trigger).get(str(condition["per"]))
                table = condition["in"]
                options = table.get(key) if isinstance(table, dict) and isinstance(key, str) else None
                if not isinstance(options, list) or value not in options:
                    return False
                continue
            if "not" in condition and value == condition["not"]:
                return False
            options = condition.get("in")
            if isinstance(options, list) and value not in options:
                return False
        elif value != condition:
            return False
    return True


def fact_problems(
    declared: dict[str, FactType],
    required: Iterable[str],
    facts: dict[str, Any],
    allowed: Mapping[str, Collection[str]] | None = None,
) -> list[tuple[Literal["violated", "inconclusive"], str]]:
    """How a record's facts disagree with the vocabulary.

    Undeclared facts are the owner's own and never a problem. A declared fact of another
    type, or a value its declaration does not list, is violated: the owner gave a declared
    word another meaning. A required fact
    that is absent (or null) leaves the record short of what the rules need, so nothing
    it should have proven can be decided: inconclusive.
    """
    problems: list[tuple[Literal["violated", "inconclusive"], str]] = []
    for name, value in facts.items():
        kind = declared.get(name)
        if kind is None:
            continue
        if value is None:
            if not kind.endswith("?"):
                problems.append(("violated", f"fact {name!r} is null"))
            continue
        expected = {"str": str, "bool": bool, "int": int}[kind.rstrip("?")]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            problems.append(("violated", f"fact {name!r} is not {kind}"))
        elif (options := (allowed or {}).get(name)) and value not in options:
            problems.append(("violated", f"fact {name!r} is {value!r}, which its declaration does not list"))
    if missing := sorted(name for name in required if facts.get(name) is None):
        problems.append(("inconclusive", f"missing required facts {missing}"))
    return problems


def declared_facts(declared: dict[str, FactType], facts: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """The facts the vocabulary declares; the rest are the owner's own and never judged."""
    return {name: value for name, value in facts.items() if name in declared}


type FactGroups = dict[str, dict[str, dict[str, tuple[str, ...]]]]


def spell_out_groups(invariant: dict[str, Any], groups: FactGroups) -> dict[str, Any]:
    """An invariant with each ``{ group = ... }`` condition replaced by ``{ in = [...] }`` over the groups' values.

    A group condition names one group or a list of them, of the fact as the condition's
    entity declares it: the trigger's, or the required entity's.
    """
    when, require = dict(invariant.get("when", {})), dict(invariant.get("require", {}))

    def spelled(entity: str | None, where: dict[str, Any]) -> dict[str, Any]:
        conditions = {}
        for fact, condition in where.items():
            if isinstance(condition, dict) and set(condition) == {"group"}:
                named = [condition["group"]] if isinstance(condition["group"], str) else list(condition["group"])
                declared = groups.get(entity or "", {}).get(fact, {})
                if unknown := [name for name in named if name not in declared]:
                    raise ValueError(f"{invariant.get('id')}: {entity}.{fact} declares no groups {unknown}")
                condition = {"in": [value for name in named for value in declared[name]]}
            conditions[fact] = condition
        return conditions

    if "where" in when:
        when["where"] = spelled(when.get("entity"), when["where"])
    if "where" in require:
        require["where"] = spelled(require.get("entity", when.get("entity")), require["where"])
    return invariant | {"when": when} | ({"require": require} if require else {})


def parse_vocabulary(document: dict[str, Any]) -> EntityVocabulary | BoundaryVocabulary:
    if document.get("kind") == "boundary":
        return BoundaryVocabulary.model_validate(document)
    return EntityVocabulary.model_validate(document)


def _unconstrained(word: EntityVocabulary) -> dict[str, Any]:
    """The machine of an entity that has none: any state, any move, never settled."""
    return {"initial": tuple(word.states), "settles_before_close": False, "transitions": (), "constrained": False}


def parse_spec(
    vocabulary: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    invariants: dict[str, Any],
    components: dict[str, Any],
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
    return Spec(
        components={component.name: component for component in component_specs},
        entities={entity.name: entity for entity in entity_specs},
        boundaries={boundary.name: boundary for boundary in boundary_specs},
        invariants=tuple(
            Invariant.model_validate(spell_out_groups(item, groups)) for item in invariants.get("invariant", [])
        ),
    )
