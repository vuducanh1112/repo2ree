from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer

from repo2ree_assurance_dossier import Cut

type Scalar = str | int | bool | None

__all__ = [
    "CommittedFile",
    "Cut",
    "Event",
    "Evidence",
    "EvidenceModel",
    "FieldChange",
    "FileChange",
    "Scalar",
    "Snapshot",
    "Source",
]


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(EvidenceModel):
    id: str
    kind: Literal["journal", "git", "store"]
    process: str
    rank: int
    instance: str | None = None
    hosts: frozenset[str]
    complete: bool
    closed: bool
    final: bool = False
    partitions: frozenset[str] | None = None
    vocabulary: str | None = None
    problems: tuple[str, ...] = ()
    origin: str | None = None
    cut: Cut | None = None

    @property
    def lineage(self) -> tuple[str, str]:
        return self.process, self.instance or ""

    @field_serializer("hosts", "partitions")
    def _sorted(self, values: frozenset[str] | None) -> list[str] | None:
        return None if values is None else sorted(values)


class Event(EvidenceModel):
    source: str
    position: int
    kind: Literal["transition", "send", "receive", "abandon", "observed"]
    owner: str
    subject: str
    key: str
    partition: str | None = None
    source_state: str | None = None
    target_state: str | None = None
    message: str | None = None
    facts: dict[str, JsonValue] = {}
    at: str | None = None
    locator: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    @property
    def ref(self) -> str:
        return self.locator or f"{self.source}#{self.position}"


class FieldChange(EvidenceModel):
    source: str
    position: int
    partition: str
    path: str
    before: str | None
    after: str | None
    operation: str
    subject: str = "Ree"
    cause: Literal["created", "operation", "external"]
    locator: str

    @property
    def ref(self) -> str:
        return self.locator


class FileChange(EvidenceModel):
    source: str
    position: int
    partition: str
    path: str
    before: str | None
    after: str | None
    operation: str
    subject: str = "Ree"
    scope: str = ""
    cause: Literal["created", "operation", "external"]
    locator: str
    storage: Literal["git", "lfs"] | None = None
    named_by: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return self.locator


class CommittedFile(EvidenceModel):
    digest: str
    size: int
    storage: Literal["git", "lfs"]
    content: bytes | None = None


class Snapshot(EvidenceModel):
    source: str
    position: int
    subject: str
    partition: str
    locator: str
    cause: Literal["created", "operation", "external"]
    operation: str | None = None
    attempt_id: str | None = None
    document: dict[str, JsonValue] | None = None
    files: dict[str, CommittedFile] = {}
    recorded: dict[str, str] | None = None

    @property
    def ref(self) -> str:
        return self.locator


class Evidence(EvidenceModel):
    sources: tuple[Source, ...]
    events: tuple[Event, ...]
    problems: tuple[str, ...] = ()
    changes: tuple[FieldChange, ...] = ()
    files: tuple[FileChange, ...] = ()
    snapshots: tuple[Snapshot, ...] = Field(default=(), exclude=True)
    witnessed: bool = False

    def source(self, source_id: str) -> Source:
        return next(source for source in self.sources if source.id == source_id)

    def ordered(self, events: list[Event]) -> list[Event]:
        ranks = {source.id: (*source.lineage, source.rank) for source in self.sources}
        return sorted(events, key=lambda event: (*ranks[event.source], event.position))
