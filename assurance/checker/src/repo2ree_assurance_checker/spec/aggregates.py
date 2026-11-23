from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal, Self

from pydantic import Field, model_validator

from repo2ree_assurance_checker.spec.base import CREATED, Name, SpecModel

FIELD_STATES: Final = ("unset", "set")
STANDINGS: Final = ("not_applicable", "missing", "current", "stale")
KEYED: Final = "[*]"
WILDCARD: Final = ".*"
ITEM: Final = "[$name]"
SLUG: Final = "{slug}"

type Operation = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
type FieldPath = Annotated[str, Field(pattern=r"^[a-z_]+(\.[a-z_]+)*(\[\*\]|\.\*)?$")]
type DocumentPath = Annotated[str, Field(pattern=r"^[a-z_]+(\.[a-z_]+|\[\*\]|\[\$name\])*$")]
type MachineKind = Literal["lifecycle", "field", "receipt"]
type EdgeOperations = dict[tuple[str, str], set[str]]


class Edge(SpecModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    by: tuple[Operation, ...] = Field(min_length=1)


class SubMachine(SpecModel):
    kind: MachineKind
    name: str
    group: str
    states: tuple[str, ...]
    edges: tuple[Edge, ...]
    bulk: tuple[Operation, ...] = ()
    keyed: bool = False
    wildcard: bool = False

    @cached_property
    def _by_edge(self) -> dict[tuple[str, str], frozenset[str]]:
        return {(edge.source, edge.target): frozenset(edge.by) for edge in self.edges}

    def allowed(self, source: str, target: str) -> frozenset[str]:
        return self._by_edge.get((source, target), frozenset())


class LifecycleTransition(SpecModel):
    source: Name = Field(alias="from")
    target: Name = Field(alias="to")
    by: tuple[Operation, ...] = Field(min_length=1)
    why: str = ""


class Lifecycle(SpecModel):
    initial: Name
    transitions: tuple[LifecycleTransition, ...] = ()

    @property
    def states(self) -> tuple[str, ...]:
        named = [self.initial, *(state for t in self.transitions for state in (t.source, t.target))]
        return tuple(dict.fromkeys(named))


class FieldMachine(SpecModel):
    group: Name
    initial: Literal["unset", "set"] | None = None
    set_by: tuple[Operation, ...] = Field(default=(), alias="set")
    changed_by: tuple[Operation, ...] = Field(default=(), alias="change")
    cleared_by: tuple[Operation, ...] = Field(default=(), alias="clear")
    files: tuple[str, ...] = ()

    @property
    def writers(self) -> frozenset[str]:
        return frozenset((*self.set_by, *self.changed_by, *self.cleared_by))


class BasisPair(SpecModel):
    recorded: DocumentPath
    now: DocumentPath


class ReceiptMachine(SpecModel):
    about: tuple[FieldPath, ...] = ()
    applies_without_declaration: bool = False
    at: DocumentPath | None = None
    basis: tuple[BasisPair, ...] | None = None
    rests_on: tuple[FieldPath, ...] = ()
    made_from: tuple[Name, ...] = ()
    cleared_by: tuple[Operation, ...] = ()
    keyed: bool = False


def field_of(fields: Iterable[str], path: str) -> str | None:
    path = path.replace(ITEM, KEYED)
    holding = []
    for name in fields:
        head = name.removesuffix(WILDCARD) if name.endswith(WILDCARD) else name
        if path == name or path.startswith(f"{head}."):
            holding.append(name)
    return max(holding, key=len, default=None)


def _derived_from_basis(document: dict[str, object]) -> dict[str, object]:
    declared = document.get("fields")
    fields = list(declared) if isinstance(declared, dict) else []
    receipts = document.get("receipts")
    if not isinstance(receipts, dict):
        return document
    locations = {
        name: str(receipt.get("at") or f"receipts.{name}")
        for name, receipt in receipts.items()
        if isinstance(receipt, dict)
    }
    derived: dict[str, object] = {}
    for name, receipt in receipts.items():
        if not isinstance(receipt, dict) or receipt.get("basis") is None:
            derived[name] = receipt
            continue
        rests_on: list[str] = []
        made_from: list[str] = []
        for pair in receipt["basis"]:
            now = pair.get("now") if isinstance(pair, dict) else None
            if not isinstance(now, str):
                continue
            if ITEM in now and not receipt.get("keyed"):
                raise ValueError(f"receipt {name}: only a keyed receipt's basis names its own item")
            source = next(
                (other for other, at in locations.items() if now == at or now.startswith((f"{at}.", f"{at}["))), None
            )
            if source is not None:
                made_from.append(source)
            elif (field := field_of(fields, now)) is not None:
                rests_on.append(field)
            else:
                raise ValueError(f"receipt {name}: its basis names {now}, which no field or receipt holds")
        spelled = {
            "rests_on": list(dict.fromkeys(rests_on)),
            "made_from": list(dict.fromkeys(made_from)),
        }
        for key, value in spelled.items():
            if key in receipt and receipt[key] != value:
                raise ValueError(f"receipt {name}: {key} is read off its basis, never stated beside it")
        derived[name] = receipt | spelled
    return document | {"receipts": derived}


TREE_FORMAT: Final = "repo2ree-ree-layout/1"


class TreeEntry(SpecModel):
    name: str
    kind: Literal["file", "directory"]
    origin: str
    capture: Literal["git", "lfs", "never"]
    description: str
    key: str | None = None
    named_by: str | None = None
    ree_root: bool = False
    children: tuple[TreeEntry, ...] = ()

    def names(self, name: str, named_by: Iterable[str]) -> bool:
        if self.named_by is not None:
            return self.named_by in {re.sub(r"\[[^]]*\]", "[*]", field) for field in named_by}
        if self.key is None:
            return name == self.name
        return re.fullmatch(re.sub(r"\\\{[a-z_]+\\\}", ".+", re.escape(self.name)), name) is not None


@dataclass(frozen=True)
class Placed:
    entry: TreeEntry
    at: str
    named: bool


def place(root: TreeEntry, path: str, named_by: Iterable[str] = ()) -> Placed:
    entry, at = root, list[str]()
    parts = PurePosixPath(path).parts
    for index, part in enumerate(parts):
        naming = named_by if index == len(parts) - 1 else ()
        children = (*entry.children, *(root.children if entry.ree_root else ()))
        named = [child for child in children if child.key is None and child.named_by is None and child.name == part]
        matched = next(iter(named), None) or next(
            (child for child in children if (child.key or child.named_by) and child.names(part, naming)), None
        )
        if matched is None:
            return Placed(entry, "/".join(at) or ".", entry.kind == "directory" and not entry.children)
        entry = matched
        at.append(matched.name)
    return Placed(entry, "/".join(at) or ".", True)


class AggregateSpec(SpecModel):
    name: Name
    summary: str
    created_by: Operation
    restored_by: Operation
    writes_nothing: tuple[Operation, ...] = ()
    receipt_entity: Name | None = None
    reviews: Name | None = None
    overlay: str | None = None
    signatures: str | None = None
    signed_by: tuple[Operation, ...] = ()
    signed_in: Name = "sealed"
    tree: str | None = None
    layout: TreeEntry | None = None
    lifecycle: Lifecycle
    fields: dict[FieldPath, FieldMachine]
    receipts: dict[Operation, ReceiptMachine] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def receipts_read_off_their_basis(cls, data: object) -> object:
        return _derived_from_basis(data) if isinstance(data, dict) else data

    @model_validator(mode="after")
    def coherent_aggregate(self) -> Self:
        if (self.tree is None) != (self.layout is None):
            raise ValueError(f"{self.name}: names the tree {self.tree}, but it was not read")
        for path, field in self.fields.items():
            if path.endswith(KEYED) == (field.initial is not None):
                raise ValueError(f"{self.name}: {path} needs an initial state exactly when it is not keyed")
            if path.endswith(WILDCARD) and field.files:
                raise ValueError(f"{self.name}: {path} stands for an object's members, which claim no files")
            if field.files and self.overlay is None:
                raise ValueError(f"{self.name}: {path} claims files, but the aggregate names no overlay")
            for file in field.files:
                if (SLUG in file) != path.endswith(KEYED) or file.count(SLUG) > 1:
                    raise ValueError(f"{self.name}: {path} claims {file}: a keyed field's files name its item once")
        claimed = [file for field in self.fields.values() for file in field.files]
        if len(claimed) != len(set(claimed)):
            raise ValueError(f"{self.name}: a file is claimed by more than one field")
        for name, receipt in self.receipts.items():
            named = (*receipt.about, *receipt.rests_on)
            if unknown := set(named) - set(self.fields):
                raise ValueError(f"{self.name}: receipt {name} names undeclared fields {sorted(unknown)}")
            if not receipt.keyed and (keyed := [path for path in named if path.endswith(KEYED)]):
                raise ValueError(f"{self.name}: receipt {name} is not keyed but names keyed fields {keyed}")
            if receipt.keyed and not any(path.endswith(KEYED) for path in receipt.about):
                raise ValueError(f"{self.name}: keyed receipt {name} must be about a keyed field")
            if unknown := set(receipt.made_from) - set(self.receipts):
                raise ValueError(f"{self.name}: receipt {name} is made from undeclared receipts {sorted(unknown)}")
            if name in receipt.made_from or any(self.receipts[other].keyed for other in receipt.made_from):
                raise ValueError(f"{self.name}: receipt {name} must be made from other, unkeyed receipts")
            if receipt.basis is not None and any(
                ITEM in pair.recorded or KEYED in pair.recorded for pair in receipt.basis
            ):
                raise ValueError(f"{self.name}: receipt {name}'s basis records values of the receipt itself")
        taking = {op for machine in self.machines for edge in machine.edges for op in edge.by}
        if moving := set(self.writes_nothing) & taking:
            raise ValueError(f"{self.name}: operations that write nothing take edges: {sorted(moving)}")
        if (self.signatures is None) != (not self.signed_by):
            raise ValueError(f"{self.name}: names signatures exactly when it names the operations that sign")
        if signing := set(self.signed_by) & set(self.writes_nothing):
            raise ValueError(f"{self.name}: operations that sign write a signature: {sorted(signing)}")
        return self

    def claim(self, path: str) -> tuple[str, str] | None:
        found: list[tuple[str, str]] = []
        for name, field in self.fields.items():
            for file in field.files:
                if SLUG not in file:
                    if path == file:
                        return name, ""
                    continue
                head, _, tail = file.partition(SLUG)
                if path.startswith(head) and path.endswith(tail) and len(path) > len(head) + len(tail):
                    slug = path[len(head) : len(path) - len(tail)]
                    if "/" not in slug:
                        found.append((name, slug))
        return min(found, key=lambda claim: len(claim[1]), default=None)

    @cached_property
    def machines(self) -> tuple[SubMachine, ...]:
        fields = [self.field_machine(path) for path in self.fields]
        receipts = [self.receipt_machine(name) for name in self.receipts]
        ordered = [self.lifecycle_machine()]
        for receipt in receipts:
            ordered += [field for field in fields if field.group == receipt.group]
            ordered.append(receipt)
        others = dict.fromkeys(field.group for field in fields if field.group not in self.receipts)
        ordered += [field for group in others for field in fields if field.group == group]
        return tuple(ordered)

    def lifecycle_machine(self) -> SubMachine:
        moves: EdgeOperations = defaultdict(set)
        moves[(CREATED, self.lifecycle.initial)].add(self.created_by)
        for transition in self.lifecycle.transitions:
            moves[(transition.source, transition.target)].update(transition.by)
        return SubMachine(
            kind="lifecycle", name="lifecycle", group="lifecycle", states=self.lifecycle.states, edges=_edges(moves)
        )

    def field_machine(self, path: str) -> SubMachine:
        field = self.fields[path]
        moves: EdgeOperations = defaultdict(set)
        if field.initial is None:
            moves[(CREATED, "set")].update((*field.set_by, self.restored_by))
        else:
            moves[(CREATED, field.initial)].add(self.created_by)
        moves[("unset", "set")].update((*field.set_by, self.restored_by))
        moves[("set", "set")].update((*field.changed_by, self.restored_by))
        moves[("set", "unset")].update((*field.cleared_by, self.restored_by))
        return SubMachine(
            kind="field",
            name=path,
            group=field.group,
            states=FIELD_STATES,
            edges=_edges(moves),
            bulk=(self.restored_by,),
            keyed=field.initial is None,
            wildcard=path.endswith(WILDCARD),
        )

    def location(self, name: str) -> str:
        return self.receipts[name].at or f"receipts.{name}"

    def receipt_machine(self, name: str) -> SubMachine:
        receipt = self.receipts[name]
        sets_about = self._writers(receipt.about, "set")
        clears_about = self._writers(receipt.about, "clear")
        basis_moves = self._writers(receipt.rests_on, "any") | {*receipt.made_from}
        moves: EdgeOperations = defaultdict(set)
        if receipt.keyed:
            moves[(CREATED, "missing")] |= sets_about
            moves[(CREATED, "current")].add(self.restored_by)
        else:
            moves[(CREATED, self.initial_standing(name))].add(self.created_by)
        moves[("not_applicable", "missing")] |= sets_about
        moves[("missing", "not_applicable")] |= clears_about
        moves[("missing", "current")].add(name)
        if receipt.applies_without_declaration or name in sets_about:
            moves[("not_applicable", "current")].add(name)
        orphaning = set() if receipt.applies_without_declaration or receipt.keyed else clears_about
        moves[("current", "stale")] |= (basis_moves | orphaning) - {name}
        reviving = sets_about if orphaning else set()
        moves[("stale", "current")] |= {name} | basis_moves | orphaning | reviving
        discarding = clears_about if receipt.keyed else set()
        for source in ("current", "stale", "missing"):
            for target in ("missing", "not_applicable"):
                if source != target:
                    moves[(source, target)].update(receipt.cleared_by)
            if source != "missing":
                moves[(source, "not_applicable")] |= discarding
        for source in STANDINGS:
            for target in STANDINGS:
                if source != target:
                    moves[(source, target)].add(self.restored_by)
        return SubMachine(
            kind="receipt",
            name=name,
            group=name,
            states=STANDINGS,
            edges=_edges(moves),
            bulk=(self.restored_by, *receipt.cleared_by),
            keyed=receipt.keyed,
        )

    def initial_standing(self, name: str) -> str:
        about = self.receipts[name].about
        return "missing" if about and all(self.fields[path].initial == "set" for path in about) else "not_applicable"

    def _writers(self, paths: Iterable[str], kind: Literal["set", "clear", "any"]) -> set[str]:
        found: set[str] = set()
        for path in paths:
            field = self.fields[path]
            found |= set({"set": field.set_by, "clear": field.cleared_by, "any": field.writers}[kind])
        return found


def _edges(moves: EdgeOperations) -> tuple[Edge, ...]:
    return tuple(
        Edge.model_validate({"from": source, "to": target, "by": sorted(ops)})
        for (source, target), ops in sorted(moves.items())
        if ops
    )
