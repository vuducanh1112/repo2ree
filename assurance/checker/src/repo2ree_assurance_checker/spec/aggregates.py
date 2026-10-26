"""Aggregate machines: one machine per part of a document an entity commits after every operation.

Not gated: the checker reports every move, and no verdict depends on them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from functools import cached_property
from typing import Annotated, Final, Literal, Self

from pydantic import Field, model_validator

from repo2ree_assurance_checker.spec.base import CREATED, Name, SpecModel

FIELD_STATES: Final = ("unset", "set")
STANDINGS: Final = ("not_applicable", "missing", "current", "stale")
KEYED: Final = "[*]"

type Operation = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
# A path into the document, relative to its subject; ``[*]`` ends a list keyed by name.
type FieldPath = Annotated[str, Field(pattern=r"^[a-z_]+(\.[a-z_]+)*(\[\*\])?$")]
type MachineKind = Literal["lifecycle", "field", "receipt"]
type EdgeOperations = dict[tuple[str, str], set[str]]


class Edge(SpecModel):
    """One edge of a sub-machine and the operations allowed to take it."""

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    by: tuple[Operation, ...] = Field(min_length=1)


class SubMachine(SpecModel):
    """One part of an aggregate, spelled out; ``bulk`` operations may take many of its edges at once."""

    kind: MachineKind
    name: str
    group: str
    states: tuple[str, ...]
    edges: tuple[Edge, ...]
    bulk: tuple[Operation, ...] = ()
    keyed: bool = False

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
    """``unset`` (absent or empty) or ``set``; a keyed field has no initial state, its items start when set."""

    group: Name
    initial: Literal["unset", "set"] | None = None
    set_by: tuple[Operation, ...] = Field(default=(), alias="set")
    changed_by: tuple[Operation, ...] = Field(default=(), alias="change")
    cleared_by: tuple[Operation, ...] = Field(default=(), alias="clear")

    @property
    def writers(self) -> frozenset[str]:
        return frozenset((*self.set_by, *self.changed_by, *self.cleared_by))


class ReceiptMachine(SpecModel):
    """A receipt's standings; its edges follow from what it depends on (``AggregateSpec.receipt_machine``)."""

    about: tuple[FieldPath, ...] = ()
    applies_without_declaration: bool = False
    rests_on: tuple[FieldPath, ...] = ()
    made_from: tuple[Name, ...] = ()
    produced_by: Operation
    cleared_by: tuple[Operation, ...] = ()
    keyed: bool = False


class AggregateSpec(SpecModel):
    name: Name
    summary: str
    created_by: Operation
    restored_by: Operation  # May move any part.
    writes_nothing: tuple[Operation, ...] = ()
    receipt_entity: Name  # Whose transitions are the receipt standings.
    lifecycle: Lifecycle
    fields: dict[FieldPath, FieldMachine]
    receipts: dict[Name, ReceiptMachine]

    @model_validator(mode="after")
    def coherent_aggregate(self) -> Self:
        for path, field in self.fields.items():
            if path.endswith(KEYED) == (field.initial is not None):
                raise ValueError(f"{self.name}: {path} needs an initial state exactly when it is not keyed")
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
        taking = {op for machine in self.machines for edge in machine.edges for op in edge.by}
        if moving := set(self.writes_nothing) & taking:
            raise ValueError(f"{self.name}: operations that write nothing take edges: {sorted(moving)}")
        return self

    @cached_property
    def machines(self) -> tuple[SubMachine, ...]:
        """Every part, in the order views draw them: the lifecycle; each receipt after the fields of its
        group; then the other fields by group, in declared order."""
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
        )

    def receipt_machine(self, name: str) -> SubMachine:
        """Applicable while what it is about is set; stale when what it rests on or is made from moves."""
        receipt = self.receipts[name]
        sets_about = self._writers(receipt.about, "set")
        clears_about = self._writers(receipt.about, "clear")
        basis_moves = self._writers(receipt.rests_on, "any") | {
            self.receipts[other].produced_by for other in receipt.made_from
        }
        moves: EdgeOperations = defaultdict(set)
        if receipt.keyed:
            moves[(CREATED, "missing")] |= sets_about
            moves[(CREATED, "current")].add(self.restored_by)
        else:
            moves[(CREATED, self.initial_standing(name))].add(self.created_by)
        moves[("not_applicable", "missing")] |= sets_about
        moves[("missing", "not_applicable")] |= clears_about
        moves[("missing", "current")].add(receipt.produced_by)
        moves[("stale", "current")].add(receipt.produced_by)
        if receipt.applies_without_declaration or receipt.produced_by in sets_about:
            moves[("not_applicable", "current")].add(receipt.produced_by)
        orphaning = set() if receipt.applies_without_declaration else clears_about
        moves[("current", "stale")] |= (basis_moves | orphaning) - {receipt.produced_by}
        for source in ("current", "stale", "missing"):
            for target in ("missing", "not_applicable"):
                if source != target:
                    moves[(source, target)].update(receipt.cleared_by)
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
        """A receipt's standing when the aggregate is created: no receipt yet, applicable or not."""
        about = self.receipts[name].about
        return "missing" if about and all(self.fields[path].initial == "set" for path in about) else "not_applicable"

    def _writers(self, paths: Iterable[str], kind: Literal["set", "clear", "any"]) -> set[str]:
        found: set[str] = set()
        for path in paths:
            field = self.fields[path]
            found |= set({"set": field.set_by, "clear": field.cleared_by, "any": field.writers}[kind])
        return found


def _edges(moves: EdgeOperations) -> tuple[Edge, ...]:
    """Edges in a stable order, each with its operations sorted; an edge no operation may take is none."""
    return tuple(
        Edge.model_validate({"from": source, "to": target, "by": sorted(ops)})
        for (source, target), ops in sorted(moves.items())
        if ops
    )
