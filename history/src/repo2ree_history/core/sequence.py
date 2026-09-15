"""Render master executions as Mermaid sequences without inventing network calls."""

from __future__ import annotations

import heapq
from collections import defaultdict
from itertools import pairwise

from repo2ree_history.core.models import (
    AuthenticationObserved,
    HistoryEvent,
    InteractionObserved,
    LayoutObserved,
    StateObserved,
    SystemExecution,
)
from repo2ree_history.core.validation import producer_key, validate_execution


def references(event: HistoryEvent) -> tuple[str, ...]:
    refs = list(event.causes)
    payload = event.payload
    if isinstance(payload, InteractionObserved) and payload.authentication_event_id:
        refs.append(payload.authentication_event_id)
    if isinstance(payload, StateObserved) and payload.boundary_event_id:
        refs.append(payload.boundary_event_id)
    return tuple(dict.fromkeys(refs))


def ordered_events(execution: SystemExecution) -> list[HistoryEvent]:
    """Deterministic topological display order; timestamps never establish causality."""
    events = {event.event_id: event for event in execution.events}
    predecessors = {event.event_id: set(references(event)) & events.keys() for event in execution.events}
    producers: dict[tuple[str, str, str], list[HistoryEvent]] = defaultdict(list)
    for event in execution.events:
        if event.sequence is not None and event.producer.epoch is not None and event.producer.instance_id is not None:
            producers[producer_key(event.producer)].append(event)
    for group in producers.values():
        for before, after in pairwise(sorted(group, key=lambda item: item.sequence or 0)):
            predecessors[after.event_id].add(before.event_id)
    successors: dict[str, list[str]] = defaultdict(list)
    remaining = {key: len(value) for key, value in predecessors.items()}
    for target, sources in predecessors.items():
        for source in sources:
            successors[source].append(target)
    ready = [key for key, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        key = heapq.heappop(ready)
        result.append(events[key])
        for target in successors[key]:
            remaining[target] -= 1
            if remaining[target] == 0:
                heapq.heappush(ready, target)
    if len(result) != len(events):
        raise ValueError("cannot draw a causal sequence: execution contains a cycle")
    return result


def escape(text: str) -> str:
    # Mermaid numeric entities keep recorded strings out of its syntax/HTML.
    return "".join(char if char.isalnum() or char in " ._-/=" else f"#{ord(char)};" for char in text)


def label(event: HistoryEvent) -> str:
    payload = event.payload
    facts = payload.model_dump(exclude_none=True)
    parts = [f"{event.event_id} [{event.sequence}] {payload.kind}"]
    if event.operation:
        parts.append(f"{event.operation.operation} attempt={event.operation.attempt_id}")
    keys = ("outcome", "state", "decision", "reason", "action", "capture_status", "after_snapshot_id", "verdict")
    parts.extend(f"{key}={facts[key]}" for key in keys if key in facts)
    if isinstance(payload, AuthenticationObserved):
        parts.append(f"session={payload.session_id} mechanism={payload.mechanism}")
    if isinstance(payload, LayoutObserved):
        boundary = payload.boundary
        parts.append(f"{boundary.event} {boundary.status}; {len(payload.entries)} inspected paths")
        parts.append(f"locks={boundary.locks_held} writers_stopped={boundary.writers_stopped}")
    if isinstance(payload, StateObserved):
        parts.append(f"{payload.projection.schema_id} consistency={payload.consistency}")
    if event.resources.ree_id:
        parts.append(f"REE={event.resources.ree_id}")
    if event.artifact_ids:
        parts.append(f"artifacts={','.join(event.artifact_ids)}")
    if event.source_refs:
        parts.append(
            "sources="
            + ", ".join(
                ref.artifact_id + ":" + str(ref.locator.model_dump(exclude_none=True)) for ref in event.source_refs
            )
        )
    if event.correlations:
        parts.append("correlated=" + ",".join(event.correlations))
    if payload.kind == "span.observed":
        parts.append(payload.name)
    return "<br/>".join(escape(part) for part in parts)


def render_sequence(execution: SystemExecution) -> str:
    issues = validate_execution(execution)
    invalid = [issue for issue in issues if issue.severity == "invalid"]
    if invalid:
        raise ValueError("invalid trace: " + "; ".join(f"{issue.code}: {issue.detail}" for issue in invalid))
    events = ordered_events(execution)
    by_id = {event.event_id: event for event in events}
    keys = sorted({producer_key(event.producer) for event in events})
    lanes = {key: f"p{index}" for index, key in enumerate(keys)}
    lines = ["sequenceDiagram", "    autonumber"]
    for key, lane in lanes.items():
        lines.append(f"    participant {lane} as {escape('/'.join(key))}")
    if not lanes:
        lines.append("    participant recorder as Recorder")
    first = next(iter(lanes.values()), "recorder")
    last = next(reversed(lanes.values()), "recorder")
    title = f"{execution.execution_id} / {execution.origin} / recording {execution.recording.status}"
    lines.append(
        f"    Note over {first},{last}: {escape(title)}<br/>"
        "One possible causal order; arrows are evidence links, not network messages"
    )
    lines.extend(
        f"    Note over {first},{last}: Limitation - {escape(reason)}" for reason in execution.recording.limitations
    )
    lines.extend(
        f"    Note over {first},{last}: INCOMPLETE - {escape(issue.code + ': ' + issue.detail)}"
        for issue in {(item.code, item.detail): item for item in issues}.values()
    )
    for event in events:
        target = lanes[producer_key(event.producer)]
        for reference in references(event):
            source = by_id.get(reference)
            if source is not None:
                origin = lanes[producer_key(source.producer)]
                lines.append(f"    {origin}-->>{target}: {escape(reference + ' supports ' + event.event_id)}")
        lines.append(f"    Note right of {target}: {label(event)}")
    return "\n".join(lines) + "\n"
