"""Validate relationships in partial recordings without discarding their evidence."""

from collections import defaultdict
from itertools import pairwise
from typing import Literal

from repo2ree_history.core.models import (
    AuthenticationObserved,
    ExecutionEnded,
    ExecutionStarted,
    GitCaptureObserved,
    HistoryModel,
    InteractionObserved,
    LayoutObserved,
    Producer,
    StateObserved,
    SystemExecution,
)


class TraceIssue(HistoryModel):
    code: str
    severity: Literal["invalid", "incomplete"]
    event_ids: tuple[str, ...] = ()
    detail: str


def producer_key(producer: Producer) -> tuple[str, str, str]:
    return producer.component, producer.instance_id or "unknown instance", producer.epoch or "unknown epoch"


def validate_execution(execution: SystemExecution) -> tuple[TraceIssue, ...]:
    """Check evidence structure, not domain contracts or unobserved executions.

    Missing references remain incomplete even in a closed recording. Timestamp
    comparisons across producers are deliberately absent: clocks may differ.
    """
    issues: list[TraceIssue] = []

    def issue(code: str, detail: str, *ids: str, incomplete: bool = False) -> None:
        issues.append(
            TraceIssue(
                code=code,
                severity="incomplete" if incomplete else "invalid",
                event_ids=ids,
                detail=detail,
            )
        )

    for field in ("workbench_id", "workbench_instance_id"):
        identities = {getattr(event.resources, field) for event in execution.events} - {None}
        if len(identities) > 1:
            issue("multiple_workbench_lifecycles", field)
    attempts: dict[str, str] = {}
    for event in execution.events:
        if event.operation is not None:
            operation = event.operation
            previous = attempts.setdefault(operation.attempt_id, operation.operation_id)
            if previous != operation.operation_id:
                issue("attempt_identity_conflict", operation.attempt_id, event.event_id)

    events = {event.event_id: event for event in execution.events}
    artifacts = {artifact.artifact_id: artifact for artifact in execution.artifacts}
    sequences: dict[tuple[str, str, str], dict[int, str]] = defaultdict(dict)
    # Edges point from effect to cause. Local sequence also establishes order.
    predecessors: dict[str, set[str]] = {event_id: set() for event_id in events}
    for event in execution.events:
        key = producer_key(event.producer)
        if event.sequence is None or event.producer.epoch is None or event.producer.instance_id is None:
            issue("producer_order_unknown", str(key), event.event_id, incomplete=True)
        elif event.sequence in sequences[key]:
            issue("duplicate_sequence", str(key), event.event_id, sequences[key][event.sequence])
        if event.sequence is not None and event.producer.epoch is not None and event.producer.instance_id is not None:
            sequences[key][event.sequence] = event.event_id
        if event.observed_at is None:
            issue("observation_time_unknown", "timestamp was not recorded", event.event_id, incomplete=True)
        for source_ref in event.source_refs:
            if source_ref.artifact_id not in artifacts:
                issue("missing_source_artifact", source_ref.artifact_id, event.event_id, incomplete=True)
        for correlation_id in event.correlations:
            if correlation_id not in events and correlation_id not in execution.related_event_ids:
                issue("missing_correlation", correlation_id, event.event_id, incomplete=True)
        for cause in event.causes:
            if cause not in events:
                issue("missing_cause", cause, event.event_id, incomplete=True)
            else:
                predecessors[event.event_id].add(cause)
        for artifact_id in event.artifact_ids:
            if artifact_id not in artifacts:
                issue("missing_artifact", artifact_id, event.event_id, incomplete=True)
        payload = event.payload
        if isinstance(payload, InteractionObserved):
            reference = payload.authentication_event_id
            if reference is None:
                continue  # Authentication requirements belong to domain contracts.
            target = events.get(reference)
            if target is None:
                issue("missing_authentication", reference, event.event_id, incomplete=True)
            elif not isinstance(target.payload, AuthenticationObserved):
                issue("authentication_type", reference, event.event_id)
            else:
                auth = target.payload
                if (
                    auth.session_id != payload.session_id
                    or auth.request_id not in (None, payload.request_id)
                    or target.resources.provider_id != event.resources.provider_id
                ):
                    issue("authentication_binding", reference, event.event_id)
                predecessors[event.event_id].add(reference)
        elif isinstance(payload, StateObserved):
            reference = payload.boundary_event_id
            if reference is None:
                if payload.consistency == "stable_boundary":
                    issue("missing_boundary", "stable state has no boundary reference", event.event_id, incomplete=True)
            elif reference not in events:
                issue("missing_boundary", reference, event.event_id, incomplete=True)
            elif not isinstance(events[reference].payload, LayoutObserved):
                issue("boundary_type", reference, event.event_id)
            else:
                predecessors[event.event_id].add(reference)
        elif isinstance(payload, GitCaptureObserved):
            if not any(
                a.kind == "git_repository" and a.repository_id == payload.repository_id for a in artifacts.values()
            ):
                issue("missing_repository", payload.repository_id, event.event_id, incomplete=True)

    for values in sequences.values():
        ordered = sorted(values)
        for before, after in pairwise(ordered):
            predecessors[values[after]].add(values[before])
            if after != before + 1:
                issue("sequence_gap", f"{before} -> {after}", values[before], values[after], incomplete=True)

    ranges = set()
    for capture in execution.recording.producers:
        key = producer_key(capture.producer)
        if key in ranges:
            issue("duplicate_producer_capture", str(key))
        ranges.add(key)
        observed = sequences.get(key, {})
        if any(n < capture.first_sequence or n > capture.last_sequence for n in observed):
            issue("sequence_outside_capture", str(key))
        count = sum(capture.first_sequence <= n <= capture.last_sequence for n in observed)
        if count != capture.last_sequence - capture.first_sequence + 1:
            issue("capture_gap", str(key), incomplete=True)
        if capture.delivery != "complete":
            issue("delivery_unconfirmed", str(key), incomplete=True)
    for key in sequences.keys() - ranges:
        issue("capture_extent_unknown", str(key), incomplete=True)

    # Kahn's algorithm avoids recursion limits for long executions.
    dependents: dict[str, list[str]] = defaultdict(list)
    remaining = {event_id: len(causes) for event_id, causes in predecessors.items()}
    for event_id, causes in predecessors.items():
        for cause in causes:
            dependents[cause].append(event_id)
    ready = [event_id for event_id, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        event_id = ready.pop()
        visited += 1
        for dependent in dependents[event_id]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if visited != len(events):
        issue("causal_cycle", "causal references contradict each other or producer order")

    starts = [event.event_id for event in execution.events if isinstance(event.payload, ExecutionStarted)]
    ends = [event.event_id for event in execution.events if isinstance(event.payload, ExecutionEnded)]
    if not starts:
        issue("missing_execution_start", "start was not observed", incomplete=True)
    if len(starts) > 1 or len(ends) > 1:
        issue("duplicate_lifecycle_boundary", "one lifecycle per execution", *starts, *ends)
    if not ends and execution.recording.status != "open":
        issue("missing_execution_end", "collection ended without a lifecycle end", incomplete=True)
    for test in execution.tests:
        for event_id in test.event_ids:
            if event_id not in events:
                issue("missing_test_event", event_id, incomplete=True)
    return tuple(issues)
