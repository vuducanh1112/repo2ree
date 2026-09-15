"""Project source documents into typed observations; never read external state."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Any

from repo2ree_history.core.evidence import Diagnostic, RecordingSnapshot, SourceDocument
from repo2ree_history.core.models import (
    EventPayload,
    FailureObservation,
    GitCaptureObserved,
    OperationCompleted,
    OperationIdentity,
    OperationStarted,
    Producer,
    Projection,
    Resources,
    SourceReference,
    SpanObserved,
    StateObserved,
    TraceContext,
)


@dataclass(frozen=True)
class EvidenceNode:
    source_refs: tuple[SourceReference, ...]
    producer: Producer
    payload: EventPayload
    resources: Resources
    operation: OperationIdentity | None
    observed_at: str | None
    trace: TraceContext | None
    keys: frozenset[tuple[str, str]]
    commit_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedEvidence:
    nodes: tuple[EvidenceNode, ...]
    diagnostics: tuple[Diagnostic, ...]


def object_document(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def trace_context(document: dict[str, Any]) -> TraceContext:
    document = object_document(document)
    values = {key: document.get(key) for key in ("trace_id", "span_id")}
    return TraceContext.model_validate(
        {key: value.removeprefix("0x") if isinstance(value, str) else value for key, value in values.items()}
    )


def identity(attrs: dict[str, Any]) -> OperationIdentity | None:
    if not all(attrs.get(key) for key in ("operation_id", "attempt_id", "operation")):
        return None
    return OperationIdentity.model_validate(
        {key: attrs.get(key) or None for key in ("operation_id", "attempt_id", "operation", "run_id")}
    )


def run_ids(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("run_id", "receipt_run_id") and isinstance(child, str) and child:
                yield child
            else:
                yield from run_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from run_ids(child)


def node(
    ref: SourceReference,
    producer: Producer,
    payload: EventPayload,
    resources: Resources,
    operation: OperationIdentity | None = None,
    observed_at: str | None = None,
    trace: TraceContext | None = None,
    keys: Iterable[tuple[str, str]] = (),
    commit_refs: tuple[str, ...] = (),
) -> EvidenceNode:
    joins = set(keys)
    for field in ("workbench_id", "workbench_instance_id", "allocation_id"):
        if value := getattr(resources, field):
            joins.add((field, value))
    if operation:
        joins.add(("attempt", operation.operation_id + "/" + operation.attempt_id))
        if operation.run_id:
            joins.add(("run", operation.run_id))
    if trace:
        joins.add(("trace", trace.trace_id))
    return EvidenceNode(
        (ref,), producer, payload, resources, operation, observed_at, trace, frozenset(joins), commit_refs
    )


def failure_from_record(document: dict[str, Any]) -> FailureObservation:
    document = object_document(document)
    value = {key: document[key] for key in ("category", "origin", "message", "retryable") if key in document}
    if document.get("details") is not None:
        value["details"] = Projection(schema_id="repo2ree.failure-details.v1", document=document["details"])
    return FailureObservation.model_validate(value)


def failure_from_span(attrs: dict[str, Any]) -> FailureObservation | None:
    values = {key.removeprefix("failure."): value for key, value in attrs.items() if key.startswith("failure.")}
    if not values:
        return None
    # Flattened span details are summaries, not a reconstruction of the original object.
    details = {key: value for key, value in values.items() if key.startswith("details.")}
    fields = {key: values[key] for key in ("category", "origin", "message", "retryable") if key in values}
    if details:
        fields["details"] = details
    return failure_from_record(fields)


def project_span(source: SourceDocument) -> NormalizedEvidence:
    span, ref = source.document, source.source
    trace = trace_context(span["context"])
    attrs = {
        key.removeprefix("repo2ree."): value
        for key, value in object_document(span.get("attributes", {})).items()
        if key.startswith("repo2ree.")
    }
    service = object_document(object_document(span.get("resource", {})).get("attributes", {}))
    component = {
        "repo2ree-api": "api",
        "repo2ree-exec": "executor",
        "repo2ree-executor": "executor",
        "repo2ree-workbench": "workbench",
        "repo2ree-supervisor": "supervisor",
        "repo2ree-provider": "provider",
    }.get(str(service.get("service.name")))
    if component is None:
        return NormalizedEvidence(
            (), (Diagnostic(code="unknown_service", detail=str(service.get("service.name")), source_refs=(ref,)),)
        )
    producer = Producer.model_validate(
        {"component": component, "instance_id": service.get("service.instance.id") or None}
    )
    resources = Resources(
        **{key: value for key, value in attrs.items() if key in Resources.model_fields and value not in (None, "")}
    )
    operation = identity(attrs)
    parent = (
        trace_context({"trace_id": trace.trace_id, "span_id": span["parent_id"]}) if span.get("parent_id") else None
    )
    payload = SpanObserved(
        name=span["name"],
        started_at=span.get("start_time"),
        ended_at=span.get("end_time"),
        parent=parent,
        links=tuple(trace_context(object_document(link).get("context", link)) for link in span.get("links", [])),
        status=object_document(span.get("status", {})).get("status_code"),
    )
    diagnostics: list[Diagnostic] = []
    commit_refs = tuple(
        attrs[key] for key in ("history.before_snapshot_id", "history.after_snapshot_id") if attrs.get(key)
    )
    if any(not isinstance(commit, str) for commit in commit_refs):
        raise ValueError("snapshot references must be strings")
    nodes = [
        node(
            ref,
            producer,
            payload,
            resources,
            operation,
            span.get("end_time"),
            trace,
            commit_refs=commit_refs,
        )
    ]
    if operation and span["name"] == "command." + operation.operation:
        nodes.append(node(ref, producer, OperationStarted(), resources, operation, span.get("start_time"), trace))
        outcome = attrs.get("status", "unknown")
        if outcome not in ("succeeded", "failed", "canceled"):
            outcome = "unknown"
        failure = None
        try:
            failure = failure_from_span(attrs)
        except (ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(
                    code="partial_failure",
                    detail=str(exc),
                    source_refs=(ref,),
                )
            )
        if failure is not None and outcome != "failed":
            diagnostics.append(
                Diagnostic(
                    code="failure_outcome_conflict",
                    severity="invalid",
                    detail="Failure details accompany a non-failed outcome",
                    source_refs=(ref,),
                )
            )
            failure = None
        nodes.append(
            node(
                ref,
                producer,
                OperationCompleted(outcome=outcome, exit_code=attrs.get("exit_code"), failure=failure),
                resources,
                operation,
                span.get("end_time"),
                trace,
            )
        )
    return NormalizedEvidence(tuple(nodes), tuple(diagnostics))


def normalize_spans(sources: tuple[SourceDocument, ...]) -> NormalizedEvidence:
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates: dict[tuple[str, str], list[SourceReference]] = defaultdict(list)
    nodes: list[EvidenceNode] = []
    diagnostics: list[Diagnostic] = []
    for source in sources:
        try:
            trace = trace_context(source.document["context"])
        except (KeyError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(code="malformed_span", severity="invalid", detail=str(exc), source_refs=(source.source,))
            )
            continue
        key = (trace.trace_id, trace.span_id)
        if key in seen:
            identical = seen[key] == source.document
            diagnostics.append(
                Diagnostic(
                    code="duplicate_span" if identical else "conflicting_span",
                    detail=" / ".join(key),
                    severity="info" if identical else "invalid",
                    source_refs=(source.source,),
                )
            )
            if identical:
                duplicates[key].append(source.source)
            continue
        seen[key] = source.document
        try:
            projected = project_span(source)
        except (KeyError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(code="malformed_span", severity="invalid", detail=str(exc), source_refs=(source.source,))
            )
            continue
        nodes.extend(projected.nodes)
        diagnostics.extend(projected.diagnostics)
    for item in nodes:
        if isinstance(item.payload, SpanObserved):
            targets = ((item.payload.parent,) if item.payload.parent else ()) + item.payload.links
            diagnostics.extend(
                Diagnostic(
                    code="missing_span_reference",
                    detail=target.trace_id + "/" + target.span_id,
                    source_refs=item.source_refs,
                )
                for target in targets
                if (target.trace_id, target.span_id) not in seen
            )
    return NormalizedEvidence(
        tuple(
            replace(item, source_refs=(*item.source_refs, *duplicates[(item.trace.trace_id, item.trace.span_id)]))
            if item.trace
            else item
            for item in nodes
        ),
        tuple(diagnostics),
    )


def normalize_states(sources: tuple[SourceDocument, ...]) -> tuple[EvidenceNode, ...]:
    nodes = []
    for source in sources:
        value = source.document
        state = object_document(value["state"])
        workbench = object_document(state.get("workbench") or {})
        resources = Resources(
            ree_id=state.get("ree_id"),
            **{
                key: workbench[key]
                for key in ("workbench_id", "workbench_instance_id", "allocation_id", "location_id")
                if workbench.get(key)
            },
        )
        document = {key: state[key] for key in ("ree_id", "status", "audit") if key in state}
        document.update(label=value.get("label"), index=value.get("index"))
        payload = StateObserved(
            projection=Projection(schema_id="repo2ree.test-state-summary.v1", document=document),
            consistency="unsynchronized",
        )
        nodes.append(
            node(
                source.source,
                Producer(component="client"),
                payload,
                resources,
                keys=(("run_reference", run) for run in run_ids(state)),
            )
        )
    return tuple(nodes)


def normalize_operations(recording: RecordingSnapshot) -> NormalizedEvidence:
    nodes: list[EvidenceNode] = []
    diagnostics: list[Diagnostic] = []
    for source in recording.operations:
        record = source.document
        context = object_document(record.get("context") or {})
        operation = identity(
            {
                **context,
                "operation": object_document(record.get("command", {})).get("operation"),
                "run_id": record.get("run_id"),
            }
        )
        if operation is None:
            diagnostics.append(
                Diagnostic(
                    code="missing_operation_identity",
                    detail="Git record has no complete operation identity",
                    source_refs=(source.source,),
                )
            )
            continue
        diagnostics.extend(
            Diagnostic(
                code="missing_commit",
                detail=f"{source.repository_id}: {field}={record[field]}",
                source_refs=(source.source,),
            )
            for field in ("before_snapshot_id", "after_snapshot_id")
            if record.get(field) and (source.repository_id, record[field]) not in recording.available_commits
        )
        failure = None
        if record.get("operation_failure"):
            try:
                failure = failure_from_record(record["operation_failure"])
            except (ValueError, TypeError) as exc:
                diagnostics.append(
                    Diagnostic(
                        code="malformed_failure", severity="invalid", detail=str(exc), source_refs=(source.source,)
                    )
                )
        payload = GitCaptureObserved(
            repository_id=source.repository_id,
            operation_failure=failure,
            **{
                key: record[key]
                for key in (
                    "selection_version",
                    "capture_status",
                    "operation_status",
                    "before_snapshot_id",
                    "after_snapshot_id",
                    "changed",
                    "capture_error",
                )
                if key in record
            },
        )
        nodes.append(
            node(
                source.source,
                Producer(component="core"),
                payload,
                Resources(ree_id=context.get("ree_id"), scope=record.get("scope", source.scope)),
                operation,
            )
        )
    return NormalizedEvidence(tuple(nodes), tuple(diagnostics))


def resolve_commits(nodes: tuple[EvidenceNode, ...], available: frozenset[tuple[str, str]]) -> NormalizedEvidence:
    repositories: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in nodes:
        if isinstance(item.payload, GitCaptureObserved) and item.operation:
            repositories[(item.operation.operation_id, item.operation.attempt_id)].add(item.payload.repository_id)
    resolved, diagnostics = [], []
    for item in nodes:
        keys = set(item.keys)
        if isinstance(item.payload, GitCaptureObserved):
            for commit in (item.payload.before_snapshot_id, item.payload.after_snapshot_id):
                if commit:
                    keys.add(("commit", item.payload.repository_id + "/" + commit))
        for commit in item.commit_refs:
            candidates = (
                repositories.get((item.operation.operation_id, item.operation.attempt_id), set())
                if item.operation
                else set()
            )
            if len(candidates) != 1:
                diagnostics.append(
                    Diagnostic(code="unresolved_commit_repository", detail=commit, source_refs=item.source_refs[:1])
                )
                continue
            repository = next(iter(candidates))
            if (repository, commit) not in available:
                diagnostics.append(
                    Diagnostic(
                        code="missing_commit", detail=repository + "/" + commit, source_refs=item.source_refs[:1]
                    )
                )
            else:
                keys.add(("commit", repository + "/" + commit))
        resolved.append(replace(item, keys=frozenset(keys)))
    return NormalizedEvidence(tuple(resolved), tuple(diagnostics))


def normalize(recording: RecordingSnapshot) -> NormalizedEvidence:
    spans = normalize_spans(recording.spans)
    nodes = list(spans.nodes)
    diagnostics = [*recording.diagnostics, *spans.diagnostics]
    for source in recording.states:
        try:
            nodes.extend(normalize_states((source,)))
        except (KeyError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(code="malformed_state", severity="invalid", detail=str(exc), source_refs=(source.source,))
            )
    for operation in recording.operations:
        try:
            projected = normalize_operations(replace(recording, operations=(operation,)))
            nodes.extend(projected.nodes)
            diagnostics.extend(projected.diagnostics)
        except (KeyError, ValueError, TypeError) as exc:
            diagnostics.append(
                Diagnostic(
                    code="malformed_operation", severity="invalid", detail=str(exc), source_refs=(operation.source,)
                )
            )
    resolved = resolve_commits(tuple(nodes), recording.available_commits)
    return NormalizedEvidence(resolved.nodes, (*diagnostics, *resolved.diagnostics))
