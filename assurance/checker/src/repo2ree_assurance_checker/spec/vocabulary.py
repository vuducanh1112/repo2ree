from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from repo2ree_assurance_checker.spec.base import FactType, Name, SpecModel


class Component(SpecModel):
    name: Name
    process: Name
    summary: str


type CatalogueTable = Literal["operations", "review_operations"]


class FactDeclaration(SpecModel):
    type: FactType
    required: bool = False
    required_in: tuple[Name, ...] = ()
    values: dict[Name, str] = Field(default_factory=dict)
    groups: dict[Name, dict[Name, str]] = Field(default_factory=dict)
    catalogue: tuple[CatalogueTable, ...] = ()

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
        if self.values and (self.groups or self.catalogue):
            raise ValueError("a fact lists its values or groups them, not both")
        if self.catalogue and self.type.rstrip("?") != "str":
            raise ValueError("only a str fact takes the catalogue's operations")
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
        return {**self.values, **{value: meaning for group in self.groups.values() for value, meaning in group.items()}}


type FactEntry = FactType | FactDeclaration


def fact_types(declared: dict[str, FactEntry]) -> dict[str, FactType]:
    return {name: entry if isinstance(entry, str) else entry.type for name, entry in declared.items()}


def allowed_values(declared: dict[str, FactEntry]) -> dict[str, tuple[str, ...]]:
    return {name: entry.allowed for name, entry in declared.items() if not isinstance(entry, str) and entry.allowed}


class EntityVocabulary(SpecModel):
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
    repeats: bool = False

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


REVIEW_PREFIX = "review_"


def with_catalogue(entry: FactEntry, catalogue: Catalogue | None) -> FactEntry:
    if isinstance(entry, str) or not entry.catalogue:
        return entry
    if catalogue is None:
        raise ValueError(f"a fact takes {list(entry.catalogue)} but the specification has no catalogue")
    tables: dict[str, dict[str, str]] = {
        table: dict(catalogue.operations if table == "operations" else catalogue.review_operations)
        for table in entry.catalogue
    }
    if clash := set(tables) & set(entry.groups):
        raise ValueError(f"a fact's own group is named like a catalogue table: {sorted(clash)}")
    return FactDeclaration.model_validate(
        entry.model_dump(exclude={"catalogue"}) | {"groups": {**entry.groups, **tables}}
    )


class Catalogue(SpecModel):
    kind: Literal["catalogue"]
    name: Name
    summary: str
    operations: dict[Name, str] = Field(min_length=1)
    review_operations: dict[Name, str] = Field(default_factory=dict)

    @property
    def names(self) -> frozenset[str]:
        return frozenset((*self.operations, *self.review_operations))

    @model_validator(mode="after")
    def reviews_reproduce_operations(self) -> Self:
        for name in self.review_operations:
            if name.removeprefix(REVIEW_PREFIX) not in self.operations or not name.startswith(REVIEW_PREFIX):
                raise ValueError(f"{name}: a review operation is {REVIEW_PREFIX!r} and the operation it reproduces")
        return self


def parse_vocabulary(document: dict[str, Any]) -> EntityVocabulary | BoundaryVocabulary | Catalogue:
    if document.get("kind") == "boundary":
        return BoundaryVocabulary.model_validate(document)
    if document.get("kind") == "catalogue":
        return Catalogue.model_validate(document)
    return EntityVocabulary.model_validate(document)
