"""What the graph is made of: vocabularies, the edges between them, and the claims on discovered sets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from repo2ree_assurance_checker.spec import Spec

# A contract by the name the graph reads it under, and where it is.
Contract = Literal["ree", "protocol", "openapi", "cli", "behaviour"]
CONTRACTS: dict[Contract, str] = {
    "ree": "contracts/ree/ree.schema.json",
    "protocol": "contracts/protocol/protocol.schema.json",
    "openapi": "contracts/openapi.json",
    "cli": "contracts/cli/cli.schema.json",
    "behaviour": "contracts/behaviour/events.schema.json",
}


class Origin(StrEnum):
    """Where a vocabulary's names are written: what a reader trusts, and what can drift."""

    SPEC = "spec"
    CONTRACT = "contract"
    SOURCE = "source"


class Relation(StrEnum):
    # The vocabulary is the union of its sources, and its extras.
    EQUALS = "equals"
    # Every name is in the union of its sources, or one of its extras.
    WITHIN = "within"
    # Generated from its sources: drawn, never checked.
    DERIVED = "derived"


@dataclass(frozen=True)
class Located:
    """A set of names as found at one place, and that place."""

    where: str
    names: frozenset[str]


class Reader:
    """What a vocabulary is read from; the context loads each document once."""

    def describe(self) -> str:
        raise NotImplementedError

    def read(self, context: Context) -> tuple[Located, ...]:
        """Every place the vocabulary is found; more than one is copies, which must agree."""
        raise NotImplementedError

    def claims(self) -> tuple[str, ...]:
        """The discovered places this reader accounts for (contract pointers, source sites)."""
        return ()


@dataclass(frozen=True)
class Vocabulary:
    name: str
    origin: Origin
    reader: Reader
    summary: str


@dataclass(frozen=True)
class Edge:
    target: str
    relation: Relation
    sources: tuple[str, ...]
    extras: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gap:
    """A discovered set nothing holds yet, kept visible until it is."""

    site: str
    reason: str


@dataclass(frozen=True)
class Ignored:
    """A discovered set of names that is no vocabulary of the graph."""

    site: str
    reason: str


@dataclass(frozen=True)
class Graph:
    roots: tuple[str, ...]
    vocabularies: tuple[Vocabulary, ...]
    edges: tuple[Edge, ...]
    gaps: tuple[Gap, ...] = ()
    ignored: tuple[Ignored, ...] = ()

    def vocabulary(self, name: str) -> Vocabulary:
        return next(item for item in self.vocabularies if item.name == name)


@dataclass
class Context:
    """The documents a check reads, each loaded once."""

    # A contract is JSON: its shape is what the readers look for, not a type.
    load_contract: Callable[[Contract], Any]
    load_spec: Callable[[], Spec]
    discover_sources: Callable[[frozenset[str]], dict[str, Located]]
    _contracts: dict[Contract, Any] = field(default_factory=dict)
    _spec: Spec | None = None
    _sources: dict[str, Located] | None = None

    def contract(self, name: Contract) -> Any:
        if name not in self._contracts:
            self._contracts[name] = self.load_contract(name)
        return self._contracts[name]

    def spec(self) -> Spec:
        if self._spec is None:
            self._spec = self.load_spec()
        return self._spec

    def roots(self) -> frozenset[str]:
        """Every name of the catalogue: what makes a set of names one discovery looks at."""
        spec = self.spec()
        return frozenset(spec.operations) | frozenset(spec.review_operations)

    def sources(self) -> dict[str, Located]:
        if self._sources is None:
            self._sources = self.discover_sources(self.roots())
        return self._sources
