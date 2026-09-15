"""Join a loaded recording using explicit identities, with no external effects."""

from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256

from repo2ree_history.core.evidence import (
    AssemblyResult,
    Attribution,
    Correlation,
    Diagnostic,
    RecordingSnapshot,
    ReeHistory,
    UnassignedEvidence,
)
from repo2ree_history.core.identity import resolve_identities
from repo2ree_history.core.models import (
    HistoryEvent,
    OperationCompleted,
    OperationStarted,
    Recording,
    SystemExecution,
    TestContext,
)
from repo2ree_history.core.normalize import EvidenceNode, normalize
from repo2ree_history.core.validation import validate_execution


def build_events(
    nodes: tuple[EvidenceNode, ...], members: tuple[int, ...], execution_id: str | None
) -> tuple[tuple[HistoryEvent, ...], tuple[Correlation, ...]]:
    events = []
    representatives: dict[tuple[str, str], str] = {}
    starts: dict[tuple[str, str], str] = {}
    key_events: dict[tuple[str, str], list[str]] = defaultdict(list)
    for index in members:
        node = nodes[index]
        event_id = f"e{index:05}"
        causes: tuple[str, ...] = ()
        if node.trace:
            trace_key = (node.trace.trace_id, node.trace.span_id)
            if isinstance(node.payload, OperationStarted):
                starts[trace_key] = event_id
            elif isinstance(node.payload, OperationCompleted) and trace_key in starts:
                causes = (starts[trace_key],)
        related = set()
        for kind, value in sorted(node.keys):
            key = ("run" if kind == "run_reference" else kind, value)
            key_events[key].append(event_id)
            if key in representatives:
                related.add(representatives[key])
            else:
                representatives[key] = event_id
        events.append(
            HistoryEvent(
                event_id=event_id,
                execution_id=execution_id,
                producer=node.producer,
                payload=node.payload,
                resources=node.resources,
                operation=node.operation,
                observed_at=datetime.fromisoformat(node.observed_at) if node.observed_at else None,
                trace_context=node.trace,
                source_refs=node.source_refs,
                artifact_ids=tuple(dict.fromkeys(ref.artifact_id for ref in node.source_refs)),
                correlations=tuple(sorted(related)),
                causes=causes,
            )
        )
    correlations = tuple(
        Correlation(kind=key[0], value=key[1], event_ids=tuple(ids))
        for key, ids in sorted(key_events.items())
        if len(ids) > 1
    )
    return tuple(events), correlations


def build_execution(
    recording: RecordingSnapshot, execution_id: str, events: tuple[HistoryEvent, ...]
) -> SystemExecution:
    manifest = recording.manifest
    return SystemExecution(
        execution_id=execution_id,
        origin="recorded",
        artifacts=recording.artifacts,
        events=events,
        related_event_ids=tuple(
            sorted({ref for event in events for ref in event.correlations} - {event.event_id for event in events})
        ),
        recording=Recording(
            status="closed",
            started_at=datetime.fromtimestamp(manifest["started"], UTC),
            finished_at=datetime.fromtimestamp(manifest["finished"], UTC),
            limitations=(
                "Partial assembly from a test arrival window; late spans may remain in service traces.",
                "Workbench association is provisional: no complete lifecycle or process epoch was recorded.",
                "Correlation is not causality. Producer order, authentication, "
                "and lifecycle boundaries remain unknown.",
                "Repository preservation consistency: "
                + ", ".join(str(repository.get("consistency", "unknown")) for repository in manifest["repositories"]),
            ),
        ),
        tests=(
            TestContext(
                invocation_id=manifest["execution_id"], runtime="python", suite="python", test_id=manifest["nodeid"]
            ),
        ),
    )


def assemble(recording: RecordingSnapshot) -> AssemblyResult:
    """Same snapshot in, same assembly out; caller owns collection and serialization."""
    normalized = normalize(recording)
    nodes = normalized.nodes
    diagnostics = list(normalized.diagnostics)
    identities, identity_issues = resolve_identities(nodes)
    diagnostics.extend(identity_issues)
    events, correlations = build_events(nodes, tuple(range(len(nodes))), None)
    lifecycle_ids = {
        identity.lifecycle: "assembled-"
        + sha256((recording.manifest["execution_id"] + "/" + "/".join(identity.lifecycle)).encode()).hexdigest()[:20]
        for identity in identities
        if identity.lifecycle is not None
    }
    events = tuple(
        event.model_copy(
            update={"execution_id": lifecycle_ids[identity.lifecycle] if identity.lifecycle is not None else None}
        )
        for event, identity in zip(events, identities, strict=True)
    )
    attributions = tuple(
        Attribution(
            event_id=event.event_id,
            ree_id=identity.ree_id,
            execution_id=event.execution_id,
            ree_support=tuple(events[i].event_id for i in identity.ree_support),
            lifecycle_support=tuple(events[i].event_id for i in identity.lifecycle_support),
        )
        for event, identity in zip(events, identities, strict=True)
    )
    executions = []
    for execution_id in sorted(lifecycle_ids.values()):
        members = tuple(event for event in events if event.execution_id == execution_id)
        execution = build_execution(recording, execution_id, members)
        executions.append(execution)
        ree_ids = {item.ree_id for item in attributions if item.execution_id == execution_id} - {None}
        ree_id = next(iter(ree_ids)) if len(ree_ids) == 1 else None
        diagnostics.extend(
            Diagnostic(
                code=issue.code,
                severity=issue.severity,
                detail=issue.detail,
                event_ids=issue.event_ids,
                execution_id=execution_id,
                ree_id=ree_id,
            )
            for issue in validate_execution(execution)
        )
        diagnostics.append(
            Diagnostic(
                code="authentication_unobserved",
                execution_id=execution_id,
                ree_id=ree_id,
                detail="No receiver-side authentication decisions are present in this assembly.",
            )
        )
    ree_histories = tuple(
        ReeHistory(
            ree_id=ree_id,
            event_ids=tuple(item.event_id for item in attributions if item.ree_id == ree_id),
            execution_ids=tuple(
                sorted(
                    {
                        item.execution_id
                        for item in attributions
                        if item.ree_id == ree_id and item.execution_id is not None
                    }
                )
            ),
            provisioning_event_ids=tuple(
                event.event_id
                for event, item in zip(events, attributions, strict=True)
                if item.ree_id == ree_id
                and event.resources.ree_id is None
                and event.resources.allocation_id is not None
                and event.operation is None
            ),
        )
        for ree_id in sorted({item.ree_id for item in attributions if item.ree_id is not None})
    )
    unassigned = [
        UnassignedEvidence(reason="unmatched_identity", source_refs=event.source_refs)
        for event, item in zip(events, attributions, strict=True)
        if item.ree_id is None and item.execution_id is None
    ]
    # Attach projection diagnostics to their surviving canonical observations.
    source_events: dict[str, list[Attribution]] = defaultdict(list)
    for event, attribution in zip(events, attributions, strict=True):
        for ref in event.source_refs:
            source_events[ref.model_dump_json()].append(attribution)
    for i, diagnostic in enumerate(diagnostics):
        matching = [item for ref in diagnostic.source_refs for item in source_events[ref.model_dump_json()]]
        rees = {item.ree_id for item in matching} - {None}
        lifecycles = {item.execution_id for item in matching} - {None}
        diagnostics[i] = diagnostic.model_copy(
            update={
                "ree_id": diagnostic.ree_id or (next(iter(rees)) if len(rees) == 1 else None),
                "execution_id": diagnostic.execution_id or (next(iter(lifecycles)) if len(lifecycles) == 1 else None),
                "event_ids": diagnostic.event_ids or tuple(dict.fromkeys(item.event_id for item in matching)),
            }
        )
    represented = {ref.model_dump_json() for node in nodes for ref in node.source_refs}
    unassigned.extend(
        UnassignedEvidence(reason=issue.code, source_refs=(ref,))
        for issue in diagnostics
        for ref in issue.source_refs
        if ref.model_dump_json() not in represented
    )
    return AssemblyResult(
        recording_root=recording.recording_root,
        artifacts=recording.artifacts,
        events=events,
        attributions=attributions,
        ree_histories=ree_histories,
        executions=tuple(executions),
        correlations=correlations,
        unassigned=tuple(unassigned),
        diagnostics=tuple(diagnostics),
    )
