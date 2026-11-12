"""Normalized evidence: owner-ordered events plus what each source can vouch for."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_serializer

from repo2ree_assurance_dossier import Cut

type Scalar = str | int | bool | None

__all__ = ["Cut", "Event", "Evidence", "EvidenceModel", "FieldChange", "FileChange", "Scalar", "Source"]


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(EvidenceModel):
    """One durable journal of one owner.

    ``partitions`` is None when the source covers every partition its owner
    touched (a process journal); a Git history covers only its own REE.

    ``final`` marks a journal its owner closed for good (a decommissioned
    deployment, the end of a test stack): an entity the specification lets
    outlive a restart must still be settled by then.

    ``cut`` is None when the source was taken after the owners it speaks for
    stopped. A snapshot of a running system carries the journal positions it
    was taken between: only what happened before the cut must be in it.
    """

    id: str
    kind: Literal["journal", "git", "store"]
    process: str
    rank: int  # Order among sources of the same process instance (journal epoch).
    # Which of a process's instances wrote it, where several run at once: the store a workbench serves.
    instance: str | None = None
    hosts: frozenset[str]  # Owners whose records this source would hold.
    complete: bool  # No gaps or unreadable records.
    closed: bool  # The owner ended the journal deliberately.
    # The owner closed it for good: it will not resume, so what it still holds open it holds forever.
    final: bool = False
    partitions: frozenset[str] | None = None
    # Provenance only: the vocabulary the owner says it wrote against. Records are judged by
    # what they hold, so a journal from an older vocabulary is checked like any other.
    vocabulary: str | None = None
    problems: tuple[str, ...] = ()
    origin: str | None = None  # Where it was collected from: a control-plane URL, or a local path.
    cut: Cut | None = None

    @property
    def lineage(self) -> tuple[str, str]:
        """The process instance whose epochs this source is one of: only its epochs are ordered by rank."""
        return self.process, self.instance or ""

    @field_serializer("hosts", "partitions")
    def _sorted(self, values: frozenset[str] | None) -> list[str] | None:
        """In a stable order, so the same evidence always writes the same report."""
        return None if values is None else sorted(values)


class Event(EvidenceModel):
    source: str
    position: int  # Order within its source.
    # "observed" is a persisted state read after the owners stopped, for reconciliation.
    kind: Literal["transition", "send", "receive", "abandon", "observed"]
    owner: str
    subject: str  # Entity name for transitions, boundary name for messages.
    key: str
    partition: str | None = None
    source_state: str | None = None
    target_state: str | None = None
    message: str | None = None
    facts: dict[str, JsonValue] = {}
    at: str | None = None
    locator: str | None = None  # A human address for the evidence (commit, file), when positions are synthetic.
    # The span active when the owner recorded this, if any. Lets views join spans; never used by the checker.
    trace_id: str | None = None
    span_id: str | None = None

    @property
    def ref(self) -> str:
        return self.locator or f"{self.source}#{self.position}"


class FieldChange(EvidenceModel):
    """One part of a committed document that a capture commit changed, witnessed from the documents themselves.

    ``path`` is relative to the document's subject, and a list keyed by name has one path
    per item (``definition.experiments[<name>]``). ``before`` and ``after`` are digests of
    the part's value, None where it is absent or empty. The commit that creates the
    document lists every part it holds.
    """

    source: str
    position: int  # The capture commit's place in its source, as its events have it.
    partition: str
    path: str
    before: str | None
    after: str | None
    operation: str  # The operation the capture commit names.
    cause: Literal["created", "operation", "external"]
    locator: str

    @property
    def ref(self) -> str:
        return self.locator


class FileChange(EvidenceModel):
    """One file a capture commit added, changed, or removed; ``before`` and ``after`` name its blob.

    ``path`` is the file's path from the REE root: a review attempt's files carry its ``reviews/<id>/``.
    The commit that creates a history lists every file.
    """

    source: str
    position: int  # The capture commit's place in its source, as its field changes have it.
    partition: str
    path: str
    before: str | None
    after: str | None
    operation: str
    cause: Literal["created", "operation", "external"]
    locator: str
    # How the commit stores it, by its .gitattributes; None once removed.
    storage: Literal["git", "lfs"] | None = None
    # The fields of the committed document whose value names it, by its path or its file name.
    named_by: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return self.locator


class Evidence(EvidenceModel):
    sources: tuple[Source, ...]
    events: tuple[Event, ...]
    problems: tuple[str, ...] = ()
    # What each capture commit changed in its committed document: aggregate evidence, never an event.
    changes: tuple[FieldChange, ...] = ()
    # What each capture commit changed in the overlay it committed: aggregate evidence, never an event.
    files: tuple[FileChange, ...] = ()

    def source(self, source_id: str) -> Source:
        return next(source for source in self.sources if source.id == source_id)

    def ordered(self, events: list[Event]) -> list[Event]:
        """Owner order: source rank, then position. Never wall-clock time."""
        ranks = {source.id: (*source.lineage, source.rank) for source in self.sources}
        return sorted(events, key=lambda event: (*ranks[event.source], event.position))
