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
    CitingEntity,
    CitingMessage,
    Spec,
)


class Model:
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
        self._later: dict[tuple[str, int], list[Event]] = defaultdict(list)
        self._earlier: dict[tuple[str, int], list[Event]] = defaultdict(list)
        self.miscited: dict[str, list[Finding]] = defaultdict(list)
        self._by_source: dict[str, list[tuple[int, list[Event]]]] | None = None
        for boundary in spec.boundaries.values():
            for citation in boundary.cites:
                self._link(boundary, citation)

    def _link(self, boundary: BoundarySpec, citation: Citation) -> None:
        record = citation.record
        if isinstance(citation.by, CitingEntity):
            self._link_across_keys(boundary, citation)
        for key, exchange in self.exchanges.get(boundary.name, {}).items():
            instance = self.instances.get(record.entity, {}).get(key)
            if instance is None:
                continue
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

    def _link_across_keys(self, boundary: BoundarySpec, citation: Citation) -> None:
        record = citation.record
        messages = {
            message.ref: (key, message)
            for key, exchange in self.exchanges.get(boundary.name, {}).items()
            for message in exchange.carrying(citation.message)
        }
        for key, instance in self.instances.get(record.entity, {}).items():
            for item in instance.reached:
                if item.state != record.reached:
                    continue
                named = item.facts.get(record.fact)
                found = messages.get(named) if isinstance(named, str) else None
                if found is not None and found[0] != key:
                    self._later[(found[1].source, found[1].position)].append(item.event)
                    self._earlier[(item.event.source, item.event.position)].append(found[1])

    def _cite(self, boundary: str, citing: Event, named: JsonValue, candidates: dict[str, Event]) -> None:
        if not isinstance(named, str) or not named:
            return
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
            and mark.lineage == origin.lineage
        ]
        if not ranks:
            return None
        return "before" if origin.rank < max(ranks) else "after"

    def _direct(self, a: Event, b: Event) -> bool | None:
        if a.source == b.source:
            return a.position < b.position
        first, second = self._sources[a.source], self._sources[b.source]
        if first.kind == second.kind == "journal" and first.lineage == second.lineage:
            return (first.rank, a.position) < (second.rank, b.position)
        return None

    def _cited(self, a: Event, b: Event) -> bool:
        for position, citing in self._cited_in(a.source):
            if position >= a.position and any(later is b or self._direct(later, b) for later in citing):
                return True
        return False

    def _cited_in(self, source: str) -> list[tuple[int, list[Event]]]:
        if self._by_source is None:
            grouped: dict[str, list[tuple[int, list[Event]]]] = defaultdict(list)
            for (cited_source, position), citing in self._later.items():
                grouped[cited_source].append((position, citing))
            self._by_source = dict(grouped)
        return self._by_source.get(source, [])

    def precedes(self, a: Event, b: Event) -> bool | None:
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
        state: str | None = None
        last: Event | None = None
        for item in instance.reached:
            before = self.precedes(item.event, moment)
            if before is None:
                return False, None
            if not before:
                break
            state, last = item.state, item.event
        entity = self.spec.entities.get(instance.subject)
        ended = entity is not None and entity.ends_with_owner and state not in instance.terminal
        if ended and last is not None and self._later_epoch(last, moment):
            return True, None
        return True, state

    def _later_epoch(self, earlier: Event, later: Event) -> bool:
        first, second = self._sources.get(earlier.source), self._sources.get(later.source)
        if first is None or second is None or not first.kind == second.kind == "journal":
            return False
        return first.lineage == second.lineage and first.rank < second.rank
