"""Pictures of the specification and of replayed evidence.

Every view is derived: the system map from the specification alone, timelines
and filmstrips from the replayed model. Nothing here decides a verdict.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from repo2ree_conformance.check import Model
from repo2ree_conformance.evidence import Event
from repo2ree_conformance.spec import (
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    MessageRequirement,
    MessageTrigger,
    Spec,
)

STEP_ORDER = ("source", "evaluation", "hardware", "runtime", "sbom", "sbom_cross_check", "test_activation")
BLOCK = 1000  # Git evidence positions: one block per capture commit (see sources.py).
PARTICIPANTS = (("api", "API"), ("supervisor", "Supervisor"), ("core", "Core"), ("git", "Git"))


def _safe(text: str) -> str:
    """Mermaid treats ';' and '#' specially in labels."""
    return re.sub(r"[;#]", ",", text)


def _short(key: str) -> str:
    return key.rsplit("-", 1)[-1][:8] if "-" in key else key[:8]


# ================================================
# System map
# ================================================


def system_map(spec: Spec) -> str:
    """Processes containing components containing the entities they own.

    Boundaries are nodes between their sender and receiver; invariants are
    dashed edges between the entities and boundaries they relate.
    """
    lines = ["flowchart LR"]
    processes: dict[str, list[str]] = defaultdict(list)
    for name, component in spec.components.items():
        processes[component.process].append(name)
    for process, components in processes.items():
        lines.append(f"  subgraph process_{process}[{process} process]")
        for member in components:
            owned = [entity.name for entity in spec.entities.values() if entity.owner == member]
            lines.append(f"    subgraph component_{member}[{member}]")
            lines.extend(f"      {entity}([{entity}])" for entity in owned)
            if not owned:
                lines.append(f"      {member}_anchor[ ]:::anchor")
            lines.append("    end")
        lines.append("  end")
    for boundary in spec.boundaries.values():
        lines.append(f"  boundary_{boundary.name}{{{{{boundary.name}}}}}:::boundary")
        lines.append(f"  component_{boundary.sender} === boundary_{boundary.name} ==> component_{boundary.receiver}")

    def node(trigger_or_requirement: object) -> str | None:
        if isinstance(trigger_or_requirement, EntityTrigger | EntityRequirement | ExclusionRequirement):
            return trigger_or_requirement.entity
        if isinstance(trigger_or_requirement, MessageTrigger | MessageRequirement):
            return f"boundary_{trigger_or_requirement.boundary}"
        return None

    for invariant in spec.invariants:
        source, target = node(invariant.when), node(invariant.require)
        if source is not None and target is not None and source != target:
            lines.append(f"  {source} -. {invariant.id} .-> {target}")
    lines += ["  classDef anchor fill:none,stroke:none", "  classDef boundary stroke-width:2px"]
    return "\n".join(lines)


# ================================================
# Timelines
# ================================================


@dataclass
class _GitSide:
    attempts: dict[str, list[Event]] = field(default_factory=lambda: defaultdict(list))
    blocks: dict[int, list[Event]] = field(default_factory=lambda: defaultdict(list))
    attempt_block: dict[str, int] = field(default_factory=dict)
    emitted: set[int] = field(default_factory=set)


def _git_side(events: list[Event]) -> _GitSide:
    side = _GitSide()
    for event in sorted(events, key=lambda item: item.position):
        block = event.position // BLOCK
        if event.subject == "Attempt":
            side.attempts[event.key].append(event)
            side.attempt_block.setdefault(event.key, block)
        else:
            side.blocks[block].append(event)
    return side


def _domain_notes(events: list[Event]) -> list[str]:
    notes: list[str] = []
    steps = [event for event in events if event.subject == "Step"]
    if steps:
        changes = ", ".join(
            f"{event.facts.get('step')} {event.source_state or 'new'}→{event.target_state}" for event in steps
        )
        notes.append(f"  Note over git: evidence: {_safe(changes)}")
    for event in events:
        if event.subject == "Ree":
            cause = "" if event.facts.get("cause") == "operation" else f" ({event.facts.get('cause')})"
            notes.append(
                f"  Note over git: REE {event.source_state or 'new'}→{event.target_state}"
                f" @{str(event.facts.get('commit', ''))[:8]}{_safe(cause)}"
            )
    return notes


def _attempt_notes(side: _GitSide, key: str) -> list[str]:
    lines: list[str] = []
    block = side.attempt_block.get(key)
    if block is None:
        return lines
    for earlier in sorted(b for b in side.blocks if b < block and b not in side.emitted):
        lines.extend(_domain_notes(side.blocks[earlier]))
        side.emitted.add(earlier)
    events = side.attempts[key]
    path = "→".join(event.target_state or "?" for event in events)
    outcome = next((event.facts.get("outcome") for event in events if "outcome" in event.facts), None)
    changed = next((event.facts.get("changed") for event in events if "changed" in event.facts), None)
    detail = f"{outcome or 'no outcome'}{', changed' if changed else ', unchanged' if changed is False else ''}"
    lines.append(f"  Note over core: attempt {_short(key)} {path} ({detail})")
    if block not in side.emitted:
        lines.extend(_domain_notes(side.blocks.get(block, [])))
        side.emitted.add(block)
    return lines


def timeline(model: Model, partition: str) -> str:
    """One REE's life across components as a sequence diagram, in evidence order."""
    events = [event for event in model.evidence.events if event.partition == partition]
    journal = model.evidence.ordered(
        [event for event in events if model.evidence.source(event.source).kind == "journal"]
    )
    side = _git_side([event for event in events if model.evidence.source(event.source).kind == "git"])
    operations: dict[str, str] = {}
    lines = ["sequenceDiagram", *(f"  participant {alias} as {label}" for alias, label in PARTICIPANTS)]
    for event in journal:
        if event.subject == "Run" and event.kind == "transition":
            operations.setdefault(event.key, str(event.facts.get("operation", "")))
            label = (
                f"run {operations[event.key]} {_short(event.key)}: {event.source_state or 'new'}→{event.target_state}"
            )
            lines.append(f"  Note over api: {_safe(label)}")
        elif event.subject == "Allocation" and event.kind == "transition":
            lines.append(f"  Note over supervisor: allocation {event.source_state or 'new'}→{event.target_state}")
        elif event.kind == "send":
            operation = _safe(str(event.facts.get("operation", event.message)))
            lines.append(f"  supervisor->>core: {operation} [{_short(event.key)}]")
            lines.extend(_attempt_notes(side, event.key))
        elif event.kind == "receive":
            status = event.facts.get("status")
            lines.append(f"  core-->>supervisor: {event.message}{f' {status}' if status else ''}")
        elif event.kind == "abandon":
            lines.append(f"  core--xsupervisor: abandoned ({_safe(str(event.facts.get('reason')))})")
    for key in sorted(side.attempts, key=lambda item: side.attempt_block[item]):
        if side.attempt_block[key] not in side.emitted:
            lines.append("  Note over core: not dispatched in this evidence")
            lines.extend(_attempt_notes(side, key))
    for block in sorted(set(side.blocks) - side.emitted):
        lines.extend(_domain_notes(side.blocks[block]))
    return "\n".join(lines)


# ================================================
# Step evidence filmstrip
# ================================================


@dataclass(frozen=True)
class Filmstrip:
    columns: tuple[str, ...]  # One per attempt, in capture order.
    rows: tuple[tuple[str, tuple[str | None, ...]], ...]  # Step name, its standing after each attempt.


def step_filmstrip(model: Model, partition: str) -> Filmstrip:
    attempts = sorted(
        (
            (min(item.event.position for item in instance.reached) // BLOCK, instance)
            for instance in model.instances.get("Attempt", {}).values()
            if instance.partition == partition
        ),
        key=lambda pair: pair[0],
    )
    steps = [instance for instance in model.instances.get("Step", {}).values() if instance.partition == partition]
    if not steps:
        return Filmstrip((), ())

    def order(name: str) -> tuple[int, str]:
        return (STEP_ORDER.index(name), "") if name in STEP_ORDER else (len(STEP_ORDER), name)

    named = sorted(((str(step.reached[0].facts.get("step")), step) for step in steps), key=lambda pair: order(pair[0]))
    columns = tuple(f"{index + 1}. {instance.facts.get('operation')}" for index, (_, instance) in enumerate(attempts))
    rows = []
    for name, step in named:
        cells: list[str | None] = []
        for block, _ in attempts:
            state = None
            for item in step.reached:
                if item.event.position < (block + 1) * BLOCK:
                    state = item.state
            cells.append(state)
        rows.append((name, tuple(cells)))
    return Filmstrip(columns, tuple(rows))


# ================================================
# Specification diff
# ================================================


@dataclass(frozen=True)
class MachineDiff:
    entity: str
    added_states: tuple[str, ...]
    removed_states: tuple[str, ...]
    added_edges: tuple[tuple[str, str], ...]
    removed_edges: tuple[tuple[str, str], ...]
    kept_edges: tuple[tuple[str, str], ...]

    @property
    def changed(self) -> bool:
        return bool(self.added_states or self.removed_states or self.added_edges or self.removed_edges)


@dataclass(frozen=True)
class SpecDiff:
    added_entities: tuple[str, ...]
    removed_entities: tuple[str, ...]
    machines: tuple[MachineDiff, ...]
    added_invariants: tuple[str, ...]
    removed_invariants: tuple[str, ...]
    changed_invariants: tuple[str, ...]
    changed_boundaries: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not (
            self.added_entities
            or self.removed_entities
            or any(machine.changed for machine in self.machines)
            or self.added_invariants
            or self.removed_invariants
            or self.changed_invariants
            or self.changed_boundaries
        )


def _edges(spec: Spec, entity: str) -> set[tuple[str, str]]:
    machine = spec.entities[entity]
    edges = {(source, target) for source, targets in machine.edges.items() for target in targets}
    return edges | {("[*]", state) for state in machine.initial}


def diff_specs(old: Spec, new: Spec) -> SpecDiff:
    shared = sorted(set(old.entities) & set(new.entities))
    machines = []
    for name in shared:
        before, after = _edges(old, name), _edges(new, name)
        machines.append(
            MachineDiff(
                entity=name,
                added_states=tuple(sorted(set(new.entities[name].states) - set(old.entities[name].states))),
                removed_states=tuple(sorted(set(old.entities[name].states) - set(new.entities[name].states))),
                added_edges=tuple(sorted(after - before)),
                removed_edges=tuple(sorted(before - after)),
                kept_edges=tuple(sorted(before & after)),
            )
        )
    old_invariants = {invariant.id: invariant for invariant in old.invariants}
    new_invariants = {invariant.id: invariant for invariant in new.invariants}
    return SpecDiff(
        added_entities=tuple(sorted(set(new.entities) - set(old.entities))),
        removed_entities=tuple(sorted(set(old.entities) - set(new.entities))),
        machines=tuple(machines),
        added_invariants=tuple(sorted(set(new_invariants) - set(old_invariants))),
        removed_invariants=tuple(sorted(set(old_invariants) - set(new_invariants))),
        changed_invariants=tuple(
            sorted(
                key for key in set(old_invariants) & set(new_invariants) if old_invariants[key] != new_invariants[key]
            )
        ),
        changed_boundaries=tuple(
            sorted(
                name
                for name in set(old.boundaries) | set(new.boundaries)
                if old.boundaries.get(name) != new.boundaries.get(name)
            )
        ),
    )


def machine_diff_chart(diff: MachineDiff) -> str:
    """The machine with added edges labelled '+ added' and removed ones '- removed'."""
    lines = ["stateDiagram-v2"]
    for source, target in diff.kept_edges:
        lines.append(f"    {source} --> {target}")
    lines.extend(f"    {source} --> {target}: + added" for source, target in diff.added_edges)
    lines.extend(f"    {source} --> {target}: - removed" for source, target in diff.removed_edges)
    lines.extend(f"    note right of {state}: added state" for state in diff.added_states)
    return "\n".join(lines)


def render_diff_markdown(diff: SpecDiff, old_digest: str, new_digest: str) -> str:
    lines = ["# Behaviour specification change", "", f"`{old_digest}` → `{new_digest}`", ""]
    if diff.empty:
        return "\n".join([*lines, "No behavioural change.", ""])
    for label, values in (
        ("Added entities", diff.added_entities),
        ("Removed entities", diff.removed_entities),
        ("Added invariants", diff.added_invariants),
        ("Removed invariants", diff.removed_invariants),
        ("Changed invariants", diff.changed_invariants),
        ("Changed boundaries", diff.changed_boundaries),
    ):
        if values:
            lines += [f"**{label}:** " + ", ".join(f"`{value}`" for value in values), ""]
    for machine in diff.machines:
        if not machine.changed:
            continue
        lines += [f"## {machine.entity}", ""]
        if machine.added_states or machine.removed_states:
            lines += [f"States added {list(machine.added_states)}, removed {list(machine.removed_states)}", ""]
        lines += ["```mermaid", machine_diff_chart(machine), "```", ""]
    return "\n".join(lines)
