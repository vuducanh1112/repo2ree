"""What the evidence can order and could have recorded: positions, epochs, citations, and cuts."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import JsonValue

from repo2ree_assurance_checker.check.replay import Exchange, Instance
from repo2ree_assurance_checker.check.results import (
    Finding,
    finding,
)
from repo2ree_assurance_checker.evidence import Cut, Event, Evidence
from repo2ree_assurance_checker.spec import (
    BoundarySpec,
    Citation,
    CitingMessage,
    Spec,
)


class Model:
    """Replayed instances and exchanges, with what the evidence can order and could have recorded."""

    def __init__(
        self,
        spec: Spec,
        evidence: Evidence,
        instances: dict[str, dict[str, Instance]],
        exchanges: dict[str, dict[str, Exchange]],
    ) -> None:
        self.spec = spec
        self.evidence = evidence
        self.instances = instances
        self.exchanges = exchanges
        self._sources = {source.id: source for source in evidence.sources}
        # Citations, as evidence of order: events recorded after an event (they name it), and before it.
        self._later: dict[tuple[str, int], list[Event]] = defaultdict(list)
        self._earlier: dict[tuple[str, int], list[Event]] = defaultdict(list)
        # Citations that name a record other than the one the evidence holds, per boundary.
        self.miscited: dict[str, list[Finding]] = defaultdict(list)
        for boundary in spec.boundaries.values():
            for citation in boundary.cites:
                self._link(boundary, citation)

    def _link(self, boundary: BoundarySpec, citation: Citation) -> None:
        record = citation.record
        for key, exchange in self.exchanges.get(boundary.name, {}).items():
            instance = self.instances.get(record.entity, {}).get(key)
            if instance is None:
                continue  # Its absence is what the invariants requiring it report.
            reached = [item for item in instance.reached if item.state == record.reached]
            messages = exchange.carrying(citation.message)
            if isinstance(citation.by, CitingMessage):
                fact = citation.by.fact
                by_identity = {str(item.facts.get(record.fact)): item.event for item in reached}
                for message in messages:
                    self._cite(boundary.name, message, message.facts.get(fact), by_identity)
            else:
                by_ref = {message.ref: message for message in messages}
                for item in reached:
                    self._cite(boundary.name, item.event, item.facts.get(record.fact), by_ref)

    def _cite(self, boundary: str, citing: Event, named: JsonValue, candidates: dict[str, Event]) -> None:
        if not isinstance(named, str) or not named:
            return  # It names nothing, so the order stays unknown.
        cited = candidates.get(named)
        if cited is None:
            if candidates:
                reason = f"names {named}, but the evidence records {sorted(candidates)}"
                subject = f"{citing.subject} {citing.key}"
                self.miscited[boundary].append(finding("violated", subject, reason, citing, *candidates.values()))
            return
        self._later[(cited.source, cited.position)].append(citing)
        self._earlier[(citing.source, citing.position)].append(cited)

    def coverage(self, owner: str, kind: str, partition: str | None, before: Event | None = None) -> tuple[bool, str]:
        """Whether a missing record is certain: (complete coverage, explanation).

        ``before`` is the moment the record must precede. A snapshot taken while
        the system ran (a source with a cut) can only vouch for what happened
        before it was taken, so without such a moment it cannot vouch at all.
        """
        covering = [
            source
            for source in self.evidence.sources
            if source.kind == kind
            and owner in source.hosts
            and (source.partitions is None or (partition is not None and partition in source.partitions))
        ]
        if not covering:
            return False, f"no {kind} evidence from {owner} covers {partition or 'this partition'}"
        if incomplete := [source.id for source in covering if not source.complete]:
            return False, f"evidence from {owner} has gaps in {', '.join(incomplete)}"
        for source in covering:
            if source.cut is None:
                continue
            if before is None:
                return False, f"{source.id} was taken while the system ran"
            placed = self.placed(before, source.cut)
            if placed is None:
                return False, f"the evidence cannot place {before.ref} against when {source.id} was taken"
            if placed != "before":
                return False, f"{before.ref} was recorded {placed} {source.id} was taken"
        return True, ""

    def placed(self, event: Event, cut: Cut) -> Literal["before", "while", "after"] | None:
        """Where a journal event falls against the cut a snapshot was taken at; None when they share no journal.

        A cut names every journal its owner had when the snapshot was taken, earlier epochs
        included. The event's own journal decides by position; otherwise its epoch decides
        against the latest epoch the cut names, the one running when the snapshot was taken.
        """
        origin = self._sources.get(event.source)
        if origin is None or origin.kind != "journal":
            return None
        if event.source in cut:
            low, high = cut[event.source]
            if event.position <= low:
                return "before"
            return "while" if event.position <= high else "after"
        ranks = [
            mark.rank
            for journal_id in cut
            if (mark := self._sources.get(journal_id)) is not None
            and mark.kind == "journal"
            and mark.process == origin.process
        ]
        if not ranks:
            return None
        return "before" if origin.rank < max(ranks) else "after"

    def _direct(self, a: Event, b: Event) -> bool | None:
        if a.source == b.source:
            return a.position < b.position
        first, second = self._sources[a.source], self._sources[b.source]
        if first.kind == second.kind == "journal" and first.process == second.process:
            return (first.rank, a.position) < (second.rank, b.position)
        return None

    def _cited(self, a: Event, b: Event) -> bool:
        """Whether a citation shows ``a`` was recorded before ``b``."""
        for later in self._later.get((a.source, a.position), ()):
            if later is b or self._direct(later, b):
                return True
        for earlier in self._earlier.get((b.source, b.position), ()):
            if earlier is a or self._direct(a, earlier):
                return True
        return False

    def precedes(self, a: Event, b: Event) -> bool | None:
        """True if ``a`` happened before ``b``, False if after, None if the evidence cannot say."""
        if a is b:
            return False
        if (direct := self._direct(a, b)) is not None:
            return direct
        if self._cited(a, b):
            return True
        if self._cited(b, a):
            return False
        return None

    def state_at(self, instance: Instance, moment: Event) -> tuple[bool, str | None]:
        """(known, state) of an instance just before ``moment``."""
        state: str | None = None
        for item in instance.reached:
            before = self.precedes(item.event, moment)
            if before is None:
                return False, None
            if not before:
                break
            state = item.state
        return True, state
