"""Pictures of the specification: the system map and the diff between two specifications.

Views of recorded evidence (behaviour traces, sequences, step standings, provenance)
live in repo2ree_assurance_traceview. Nothing here decides a verdict.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from repo2ree_assurance_checker.spec import (
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    MessageRequirement,
    MessageTrigger,
    Spec,
)


def _safe(text: str) -> str:
    """Mermaid treats ';' and '#' specially in labels."""
    return re.sub(r"[;#]", ",", text)


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
