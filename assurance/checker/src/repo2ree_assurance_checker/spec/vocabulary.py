"""The vocabulary: the words owners emit for each entity and exchange, published to the product."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from repo2ree_assurance_checker.spec.base import FactType, Name, SpecModel


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
    values: dict[Name, str] = Field(default_factory=dict)
    groups: dict[Name, dict[Name, str]] = Field(default_factory=dict)

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
    facts: dict[Name, FactEntry] = Field(default_factory=dict)

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
    facts: dict[Name, dict[Name, FactEntry]] = Field(default_factory=dict)

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


def parse_vocabulary(document: dict[str, Any]) -> EntityVocabulary | BoundaryVocabulary:
    if document.get("kind") == "boundary":
        return BoundaryVocabulary.model_validate(document)
    return EntityVocabulary.model_validate(document)
