"""Aggregate machines against the evidence: every move of every part, counted, judged, and replayed per instance.

Nothing here changes a verdict.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from repo2ree_assurance_checker.check.results import (
    AggregateHistory,
    AggregateResult,
    Finding,
    MoveCount,
    Part,
    StateStep,
)
from repo2ree_assurance_checker.evidence import Evidence, FieldChange
from repo2ree_assurance_checker.spec import CREATED, KEYED, AggregateSpec, Spec, SubMachine

# Where a move was made between operations rather than by one.
EXTERNAL = "(between operations)"


@dataclass(frozen=True)
class Move:
    """One part of one aggregate instance moving along one edge, by one operation."""

    machine: SubMachine
    partition: str
    item: str  # The item of a keyed machine; empty otherwise.
    source: str
    target: str
    operation: str
    ref: str
    position: int

    @property
    def part(self) -> str:
        return f"{self.machine.name.removesuffix(KEYED)}[{self.item}]" if self.item else self.machine.name

    @property
    def allowed(self) -> bool:
        return self.operation in self.machine.allowed(self.source, self.target)


def check_aggregates(spec: Spec, evidence: Evidence) -> tuple[AggregateResult, ...]:
    return tuple(check_aggregate(aggregate, evidence) for aggregate in spec.aggregates.values())


def check_aggregate(aggregate: AggregateSpec, evidence: Evidence) -> AggregateResult:
    found = moves(aggregate, evidence)
    tally = Counter((m.machine.kind, m.machine.name, m.source, m.target, m.operation, m.allowed) for m in found)
    return AggregateResult(
        aggregate=aggregate.name,
        instances=len({move.partition for move in found if move.machine.kind == "lifecycle"}),
        moves=tuple(
            MoveCount(kind=kind, machine=name, source=source, target=target, operation=op, count=count, allowed=ok)
            for (kind, name, source, target, op, ok), count in sorted(tally.items())
        ),
        findings=tuple(
            Finding(
                verdict="violated",
                subject=f"{aggregate.name} {move.partition} {move.part}",
                reason=f"{move.source} -> {move.target} by {move.operation}, which no edge allows",
                evidence=(move.ref,),
            )
            for move in found
            if not move.allowed
        ),
    )


def histories(spec: Spec, evidence: Evidence) -> tuple[AggregateHistory, ...]:
    """Each aggregate instance's states, step by step, as its operations moved it."""
    replayed: list[AggregateHistory] = []
    for aggregate in spec.aggregates.values():
        by_instance: dict[str, list[Move]] = defaultdict(list)
        for move in moves(aggregate, evidence):
            by_instance[move.partition].append(move)
        replayed += [history(aggregate, instance, found) for instance, found in sorted(by_instance.items())]
    return tuple(replayed)


def history(aggregate: AggregateSpec, instance: str, found: Sequence[Move]) -> AggregateHistory:
    """One step per capture and operation; the standings first audited belong to the step that created it."""
    ordered = sorted(found, key=lambda move: move.position)
    creation = next(((m.ref, m.operation) for m in ordered if m.operation == aggregate.created_by), None)

    def step_of(move: Move) -> tuple[str, str]:
        return creation if creation and move.operation == aggregate.created_by else (move.ref, move.operation)

    steps: dict[tuple[str, str], list[Move]] = defaultdict(list)
    for move in ordered:
        steps[step_of(move)].append(move)
    states: dict[str, str] = {}
    replayed: list[StateStep] = []
    for index, ((ref, operation_name), step) in enumerate(steps.items()):
        states |= {move.part: move.target for move in step}
        moved = dict.fromkeys(move.part for move in step if index or move.source != CREATED)
        replayed.append(StateStep(operation=operation_name, ref=ref, states=dict(states), moved=tuple(moved)))
    drawn = {machine.name: index for index, machine in enumerate(aggregate.machines)}
    first: dict[str, Move] = {}
    for move in ordered:
        first.setdefault(move.part, move)
    parts = sorted(first.values(), key=lambda move: (drawn.get(move.machine.name, len(drawn)), move.position))
    return AggregateHistory(
        aggregate=aggregate.name,
        instance=instance,
        parts=tuple(
            Part(name=m.part, machine=m.machine.name, item=m.item, kind=m.machine.kind, group=m.machine.group)
            for m in parts
        ),
        steps=tuple(replayed),
    )


def moves(aggregate: AggregateSpec, evidence: Evidence) -> list[Move]:
    machines = aggregate.machines
    lifecycle = next(machine for machine in machines if machine.kind == "lifecycle")
    return [
        *lifecycle_moves(aggregate, lifecycle, evidence),
        *field_moves(aggregate, [machine for machine in machines if machine.kind == "field"], evidence.changes),
        *receipt_moves(
            aggregate, {machine.name: machine for machine in machines if machine.kind == "receipt"}, evidence
        ),
    ]


def lifecycle_moves(aggregate: AggregateSpec, machine: SubMachine, evidence: Evidence) -> Iterator[Move]:
    """The entity's own transitions that change its state; a capture that keeps it there is no lifecycle move."""
    events = [e for e in evidence.events if e.subject == aggregate.name and e.kind == "transition"]
    for event in evidence.ordered(events):
        if event.source_state != event.target_state and event.partition and event.target_state:
            yield Move(
                machine=machine,
                partition=event.partition,
                item="",
                source=event.source_state or CREATED,
                target=event.target_state,
                operation=operation(aggregate, event.facts.get("cause"), event.facts.get("operation")),
                ref=event.ref,
                position=event.position,
            )


def field_moves(
    aggregate: AggregateSpec, fields: Sequence[SubMachine], changes: Iterable[FieldChange]
) -> Iterator[Move]:
    """Each instance's fields, from the document parts its capture commits changed."""
    by_partition: dict[str, list[FieldChange]] = defaultdict(list)
    for change in changes:
        by_partition[change.partition].append(change)
    for partition, found in sorted(by_partition.items()):
        yield from _instance_fields(aggregate, fields, partition, sorted(found, key=lambda change: change.position))


def _instance_fields(
    aggregate: AggregateSpec, fields: Sequence[SubMachine], partition: str, ordered: Sequence[FieldChange]
) -> Iterator[Move]:
    """An unkeyed field starts where the creating commit left it, set or not; a keyed item when first set."""

    def move(machine: SubMachine, item: str, source: str, target: str, change: FieldChange) -> Move:
        return Move(
            machine=machine,
            partition=partition,
            item=item,
            source=source,
            target=target,
            operation=operation(aggregate, change.cause, change.operation),
            ref=change.ref,
            position=change.position,
        )

    creation = next((change for change in ordered if change.cause == "created"), None)
    for machine in fields:
        if machine.keyed:
            items = re.compile(re.escape(machine.name.removesuffix(KEYED)) + r"\[(?P<item>[^\]]+)\]$")
            seen: set[str] = set()
            for change in ordered:
                if (match := items.match(change.path)) is not None:
                    item = match["item"]
                    source = _held(change.before) if item in seen else CREATED
                    seen.add(item)
                    yield move(machine, item, source, _held(change.after), change)
            continue
        own = [change for change in ordered if change.path == machine.name]
        if creation is not None:
            held = any(change.cause == "created" for change in own)
            yield move(machine, "", CREATED, "set" if held else "unset", creation)
        for change in own:
            if change.cause != "created":
                yield move(machine, "", _held(change.before), _held(change.after), change)


def _held(digest: str | None) -> str:
    return "unset" if digest is None else "set"


def receipt_moves(aggregate: AggregateSpec, receipts: Mapping[str, SubMachine], evidence: Evidence) -> Iterator[Move]:
    """Each receipt's standings, one machine per kind; a kind no machine describes allows nothing."""
    events = [e for e in evidence.events if e.subject == aggregate.receipt_entity and e.kind == "transition"]
    for event in evidence.ordered(events):
        kind = str(event.facts.get("kind", ""))
        machine = receipts.get(kind) or SubMachine(
            kind="receipt", name=kind or "(no kind)", group=kind, states=(), edges=()
        )
        # The vocabulary names a keyed receipt's step "<kind>:<item>".
        step = str(event.facts.get("step", ""))
        yield Move(
            machine=machine,
            partition=event.partition or "",
            item=step.partition(":")[2] if machine.keyed else "",
            source=event.source_state or CREATED,
            target=event.target_state or "",
            operation=operation(aggregate, event.facts.get("cause"), event.facts.get("operation")),
            ref=event.ref,
            position=event.position,
        )


def operation(aggregate: AggregateSpec, cause: JsonValue, named: JsonValue) -> str:
    """The operation a move is counted under: the one its capture names.

    A receipt's first audited standing ("baseline") is the one the aggregate was created
    with; a change found between captures has no operation.
    """
    if cause == "baseline":
        return aggregate.created_by
    if cause == "external" or not named:
        return EXTERNAL
    return str(named)
