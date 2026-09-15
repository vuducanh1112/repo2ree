"""Explicit values exchanged between the pure core and imperative shell."""

from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import model_validator

from repo2ree_history.core.models import (
    Artifact,
    HistoryEvent,
    HistoryModel,
    Identifier,
    SourceReference,
    SystemExecution,
)


class Diagnostic(HistoryModel):
    code: str
    detail: str
    severity: Literal["info", "incomplete", "invalid"] = "incomplete"
    ree_id: Identifier | None = None
    execution_id: Identifier | None = None
    source_refs: tuple[SourceReference, ...] = ()
    event_ids: tuple[str, ...] = ()


class UnassignedEvidence(HistoryModel):
    reason: str
    source_refs: tuple[SourceReference, ...]


class Correlation(HistoryModel):
    kind: str
    value: str
    event_ids: tuple[str, ...]


class Attribution(HistoryModel):
    event_id: Identifier
    ree_id: Identifier | None = None
    execution_id: Identifier | None = None
    ree_support: tuple[Identifier, ...] = ()
    lifecycle_support: tuple[Identifier, ...] = ()


class ReeHistory(HistoryModel):
    ree_id: Identifier
    event_ids: tuple[Identifier, ...]
    execution_ids: tuple[Identifier, ...]
    provisioning_event_ids: tuple[Identifier, ...] = ()


class AssemblyResult(HistoryModel):
    schema_version: Literal[2] = 2
    events: tuple[HistoryEvent, ...]
    attributions: tuple[Attribution, ...] = ()
    ree_histories: tuple[ReeHistory, ...] = ()
    recording_root: str
    artifacts: tuple[Artifact, ...]
    executions: tuple[SystemExecution, ...]
    unassigned: tuple[UnassignedEvidence, ...]
    diagnostics: tuple[Diagnostic, ...]
    correlations: tuple[Correlation, ...] = ()

    @model_validator(mode="after")
    def coherent_views(self) -> Self:
        events = {event.event_id: event for event in self.events}
        if len(events) != len(self.events):
            raise ValueError("duplicate canonical event ID")
        execution_ids = {execution.execution_id for execution in self.executions}
        if len(execution_ids) != len(self.executions):
            raise ValueError("duplicate execution ID")
        if len({history.ree_id for history in self.ree_histories}) != len(self.ree_histories):
            raise ValueError("duplicate REE history")
        for execution in self.executions:
            if any(events.get(event.event_id) != event for event in execution.events):
                raise ValueError("execution view differs from canonical evidence")
            if not set(execution.related_event_ids) <= events.keys():
                raise ValueError("execution references unknown external evidence")
        for history in self.ree_histories:
            if not set(history.event_ids) <= events.keys() or not set(history.execution_ids) <= execution_ids:
                raise ValueError("REE history references unknown evidence")
            if not set(history.provisioning_event_ids) <= set(history.event_ids):
                raise ValueError("provisioning ancestry is outside REE history")
        for item in self.attributions:
            if item.event_id not in events or not {*item.ree_support, *item.lifecycle_support} <= events.keys():
                raise ValueError("attribution references unknown evidence")
            if events[item.event_id].execution_id != item.execution_id:
                raise ValueError("attribution differs from canonical execution identity")
        return self


@dataclass(frozen=True)
class SourceDocument:
    document: dict[str, Any]
    source: SourceReference


@dataclass(frozen=True)
class DocumentBatch:
    documents: tuple[SourceDocument, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class GitDocument:
    document: dict[str, Any]
    source: SourceReference
    repository_id: str
    scope: str


@dataclass(frozen=True)
class RecordingSnapshot:
    recording_root: str
    manifest: dict[str, Any]
    artifacts: tuple[Artifact, ...]
    spans: tuple[SourceDocument, ...] = ()
    states: tuple[SourceDocument, ...] = ()
    operations: tuple[GitDocument, ...] = ()
    available_commits: frozenset[tuple[str, str]] = frozenset()
    diagnostics: tuple[Diagnostic, ...] = ()
