"""The rules on the vocabulary.

Each entity's machine, and each boundary's exchange with the records that cite each other.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from repo2ree_assurance_checker.spec.base import FactType, Name, SpecModel


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
    facts: dict[Name, FactType] = Field(default_factory=dict)
    # The facts every transition into a state must carry, by state.
    required: dict[Name, tuple[Name, ...]] = Field(default_factory=dict)
    # The only values a fact may take, for the facts that list them; what each means; and how they group.
    allowed: dict[Name, tuple[str, ...]] = Field(default_factory=dict)
    meanings: dict[Name, dict[str, str]] = Field(default_factory=dict)
    groups: dict[Name, dict[Name, tuple[str, ...]]] = Field(default_factory=dict)
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
    facts: dict[Name, dict[Name, FactType]] = Field(default_factory=dict)
    # The facts every record of a message must carry, by message.
    required: dict[Name, tuple[Name, ...]] = Field(default_factory=dict)
    # The only values a fact may take, by message, for the facts that list them.
    allowed: dict[Name, dict[Name, tuple[str, ...]]] = Field(default_factory=dict)
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
