from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from repo2ree_assurance_checker.spec import Spec

Contract = Literal["ree", "protocol", "openapi", "cli", "behaviour", "exercise"]
CONTRACTS: dict[Contract, str] = {
    "ree": "contracts/ree/ree.schema.json",
    "protocol": "contracts/protocol/protocol.schema.json",
    "openapi": "contracts/openapi.json",
    "cli": "contracts/cli/cli.schema.json",
    "behaviour": "contracts/behaviour/events.schema.json",
    "exercise": "contracts/exercise/exercise.schema.json",
}


class Origin(StrEnum):
    SPEC = "spec"
    CONTRACT = "contract"
    SOURCE = "source"


class Relation(StrEnum):
    EQUALS = "equals"
    WITHIN = "within"
    DERIVED = "derived"


@dataclass(frozen=True)
class Located:
    where: str
    names: frozenset[str]


class Reader:
    def describe(self) -> str:
        raise NotImplementedError

    def read(self, context: Context) -> tuple[Located, ...]:
        raise NotImplementedError

    def claims(self) -> tuple[str, ...]:
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
class Ignored:
    site: str
    reason: str


@dataclass(frozen=True)
class Graph:
    roots: tuple[str, ...]
    vocabularies: tuple[Vocabulary, ...]
    edges: tuple[Edge, ...]
    ignored: tuple[Ignored, ...] = ()

    def vocabulary(self, name: str) -> Vocabulary:
        return next(item for item in self.vocabularies if item.name == name)


@dataclass
class Context:
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
        spec = self.spec()
        return frozenset(spec.operations) | frozenset(spec.review_operations)

    def sources(self) -> dict[str, Located]:
        if self._sources is None:
            self._sources = self.discover_sources(self.roots())
        return self._sources
