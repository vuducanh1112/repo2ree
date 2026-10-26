"""Normalized evidence: owner-ordered events plus what each source can vouch for."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_serializer

from repo2ree_assurance_dossier import Cut

type Scalar = str | int | bool | None

__all__ = ["Cut", "Event", "Evidence", "EvidenceModel", "FieldChange", "Scalar", "Source"]


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
    rank: int  # Order among sources of the same process (journal epoch).
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


class Evidence(EvidenceModel):
    sources: tuple[Source, ...]
    events: tuple[Event, ...]
    problems: tuple[str, ...] = ()
    # What each capture commit changed in its committed document: aggregate evidence, never an event.
    changes: tuple[FieldChange, ...] = ()

    def source(self, source_id: str) -> Source:
        return next(source for source in self.sources if source.id == source_id)

    def ordered(self, events: list[Event]) -> list[Event]:
        """Owner order: source rank, then position. Never wall-clock time."""
        ranks = {source.id: (source.process, source.rank) for source in self.sources}
        return sorted(events, key=lambda event: (*ranks[event.source], event.position))
