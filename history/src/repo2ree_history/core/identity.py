"""Attribute observations without merging lifecycles through historical evidence."""

from collections import defaultdict
from dataclasses import dataclass

from repo2ree_history.core.evidence import Diagnostic
from repo2ree_history.core.normalize import EvidenceNode

type Lifecycle = tuple[str, str]


@dataclass(frozen=True)
class Identity:
    ree_id: str | None
    lifecycle: Lifecycle | None
    ree_support: tuple[int, ...] = ()
    lifecycle_support: tuple[int, ...] = ()


def lifecycle_anchors(nodes: tuple[EvidenceNode, ...]) -> tuple[Lifecycle | None, ...]:
    instances: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        resources = node.resources
        if resources.workbench_id and resources.workbench_instance_id:
            instances[resources.workbench_id].add(resources.workbench_instance_id)
    anchors: list[Lifecycle | None] = []
    for node in nodes:
        resources = node.resources
        if resources.workbench_instance_id:
            anchors.append(("instance", resources.workbench_instance_id))
        elif resources.workbench_id:
            known = instances[resources.workbench_id]
            if len(known) == 1:
                anchors.append(("instance", next(iter(known))))
            elif not known:
                anchors.append(("workbench", resources.workbench_id))
            else:
                anchors.append(None)
        else:
            anchors.append(None)
    return tuple(anchors)


def ownership_groups(nodes: tuple[EvidenceNode, ...], *, lifecycle: bool) -> tuple[tuple[int, ...], ...]:
    """Only ownership establishes equivalence; references and traces stay edges."""
    instances: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        if node.resources.workbench_id and node.resources.workbench_instance_id:
            instances[node.resources.workbench_id].add(node.resources.workbench_instance_id)
    owners: dict[tuple[str, str], list[int]] = defaultdict(list)
    keys_by_node = []
    for index, node in enumerate(nodes):
        keys = {
            key
            for key in node.keys
            if key[0] in {"attempt", "run", "allocation_id", "workbench_id", "workbench_instance_id"}
            and not (lifecycle and key[0] == "workbench_id" and len(instances[key[1]]) > 1)
        }
        keys_by_node.append(keys)
        for key in keys:
            owners[key].append(index)
    groups = []
    visited: set[int] = set()
    for index in range(len(nodes)):
        if index in visited:
            continue
        pending = [index]
        members = []
        while pending:
            member = pending.pop()
            if member in visited:
                continue
            visited.add(member)
            members.append(member)
            for key in keys_by_node[member]:
                pending.extend(owners.pop(key, ()))
        groups.append(tuple(sorted(members)))
    return tuple(groups)


def attribute[T: (str, Lifecycle)](
    nodes: tuple[EvidenceNode, ...], values: tuple[T | None, ...], *, lifecycle: bool
) -> tuple[tuple[T | None, ...], tuple[tuple[int, ...], ...], tuple[Diagnostic, ...]]:
    resolved = list(values)
    supports: list[tuple[int, ...]] = [() for _ in nodes]
    diagnostics = []
    ambiguous: set[int] = set()
    for members in ownership_groups(nodes, lifecycle=lifecycle):
        candidates = {values[i] for i in members} - {None}
        if len(candidates) > 1:
            ambiguous.update(members)
            diagnostics.append(
                Diagnostic(
                    code="identity_conflict",
                    severity="invalid",
                    detail="Conflicting " + ("lifecycle" if lifecycle else "REE") + " ownership",
                    source_refs=tuple(dict.fromkeys(ref for i in members for ref in nodes[i].source_refs)),
                )
            )
            continue
        if len(candidates) == 1:
            value = next(iter(candidates))
            support = tuple(i for i in members if values[i] is not None)
            for i in members:
                if values[i] is None:
                    resolved[i] = value
                    supports[i] = support
    # A trace can attach anonymous detail to a unique owner. It cannot override
    # an explicit identity, resolve an ownership conflict, or merge lifecycles.
    traces: dict[str, list[int]] = defaultdict(list)
    for i, node in enumerate(nodes):
        if node.trace:
            traces[node.trace.trace_id].append(i)
    known = tuple(resolved)
    for trace_members in traces.values():
        candidates = {known[i] for i in trace_members} - {None}
        if len(candidates) != 1:
            continue
        value = next(iter(candidates))
        support = tuple(
            sorted({anchor for i in trace_members if known[i] is not None for anchor in (supports[i] or (i,))})
        )
        for i in trace_members:
            if resolved[i] is None and i not in ambiguous:
                resolved[i] = value
                supports[i] = support
    return tuple(resolved), tuple(supports), tuple(diagnostics)


def resolve_identities(nodes: tuple[EvidenceNode, ...]) -> tuple[tuple[Identity, ...], tuple[Diagnostic, ...]]:
    ree_ids, ree_support, ree_issues = attribute(nodes, tuple(node.resources.ree_id for node in nodes), lifecycle=False)
    lifecycles, lifecycle_support, lifecycle_issues = attribute(nodes, lifecycle_anchors(nodes), lifecycle=True)
    return tuple(
        Identity(ree, lifecycle, ree_refs, lifecycle_refs)
        for ree, lifecycle, ree_refs, lifecycle_refs in zip(
            ree_ids, lifecycles, ree_support, lifecycle_support, strict=True
        )
    ), (*ree_issues, *lifecycle_issues)
