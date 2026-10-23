"""Check evidence against the specification; the same inputs always give the same verdicts.

Absence is a violation only where a complete source covering the subject could
have recorded it, and order is asserted only where the evidence establishes it.
Everything else that cannot be decided is inconclusive, never a pass.

The checker judges only what the vocabulary declares. Owners may record more (other
subjects, other facts); that is reported as extras and never changes a verdict. A
declared fact of the wrong type is violated; a required one that is missing leaves the
record unable to prove anything, so it is inconclusive.

Order comes from three places only: positions within one source, epochs and
positions within one process's journals, and citations (``cites`` in a boundary
spec): a record that names another was written after it. Wall-clock time is
never used, and nothing is assumed about where the receiver did its work.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue

from repo2ree_assurance_checker.evidence import Cut, Event, Evidence, EvidenceModel, Source
from repo2ree_assurance_checker.spec import (
    CREATED,
    OWN_KEY,
    BoundarySpec,
    Citation,
    CitingMessage,
    EntityRequirement,
    EntitySpec,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    Spec,
    absent,
    declared_facts,
    fact_problems,
    matches,
)

type Verdict = Literal["passed", "violated", "inconclusive", "not_triggered"]
type FindingVerdict = Literal["violated", "inconclusive"]

INITIAL = CREATED


class Finding(EvidenceModel):
    verdict: FindingVerdict
    subject: str
    reason: str
    evidence: tuple[str, ...] = ()


class RuleResult(EvidenceModel):
    rule: str
    kind: Literal["evidence", "machine", "boundary", "invariant", "reconciliation"]
    summary: str
    triggered: int = 0
    open: int = 0
    findings: tuple[Finding, ...] = ()

    @property
    def verdict(self) -> Verdict:
        if any(finding.verdict == "violated" for finding in self.findings):
            return "violated"
        if self.findings:
            return "inconclusive"
        return "passed" if self.triggered else "not_triggered"


class Extra(EvidenceModel):
    """What owners recorded beyond the vocabulary: a subject it does not declare, or a fact of one it does."""

    subject: str
    fact: str | None = None  # None: the whole subject is undeclared.
    count: int
    evidence: tuple[str, ...] = ()


class Coverage(EvidenceModel):
    """How often each declared edge and message was observed; zero marks a gap."""

    transitions: dict[str, dict[str, int]]
    messages: dict[str, dict[str, int]]


class CheckResult(EvidenceModel):
    spec_digest: str
    sources: tuple[Source, ...]
    rules: tuple[RuleResult, ...]
    coverage: Coverage
    # The contract the evidence was judged against; a journal's own stamp is provenance only.
    vocabulary_digest: str = ""
    extras: tuple[Extra, ...] = ()

    @property
    def verdict(self) -> Verdict:
        """A check in which no behavioural rule triggered proves nothing, so it is inconclusive."""
        verdicts = {rule.verdict for rule in self.rules}
        if "violated" in verdicts:
            return "violated"
        if "inconclusive" in verdicts:
            return "inconclusive"
        if not any(rule.triggered for rule in self.rules if rule.kind not in {"evidence", "reconciliation"}):
            return "inconclusive"
        return "passed"

    @property
    def exit_code(self) -> int:
        return {"violated": 1, "inconclusive": 2}.get(self.verdict, 0)


@dataclass
class Reached:
    source_state: str | None
    state: str
    facts: dict[str, JsonValue]
    event: Event


@dataclass
class Instance:
    subject: str
    key: str
    partition: str | None
    terminal: frozenset[str]
    current: str | None = None
    facts: dict[str, JsonValue] = field(default_factory=dict)
    reached: list[Reached] = field(default_factory=list)

    @property
    def settled(self) -> bool:
        return self.current in self.terminal


@dataclass
class Exchange:
    key: str
    partition: str | None
    events: list[Event] = field(default_factory=list)

    @property
    def request(self) -> Event | None:
        return next((event for event in self.events if event.kind == "send"), None)

    @property
    def outcome(self) -> Event | None:
        return next((event for event in self.events if event.kind in {"receive", "abandon"}), None)

    def carrying(self, message: str) -> list[Event]:
        return [event for event in self.events if event.message == message]


@dataclass
class Occurrence:
    subject: str
    key: str
    partition: str | None
    facts: dict[str, JsonValue]
    event: Event
    instance: Instance | None = None
    index: int = 0


def edge(source: str | None, target: str) -> str:
    return f"{source or INITIAL} -> {target}"


def _finding(verdict: FindingVerdict, subject: str, reason: str, *events: Event) -> Finding:
    return Finding(verdict=verdict, subject=subject, reason=reason, evidence=tuple(event.ref for event in events))


# ================================================
# Replay
# ================================================


def replay_entity(
    spec: EntitySpec, events: list[Event], evidence: Evidence
) -> tuple[dict[str, Instance], RuleResult, dict[str, int]]:
    findings: list[Finding] = []
    # An unconstrained entity declares no edges, so there is nothing for its evidence to cover.
    counts: dict[str, int] = {}
    if spec.constrained:
        counts = {edge(None, state): 0 for state in spec.initial}
        for source_state, targets in spec.edges.items():
            counts.update({edge(source_state, target): 0 for target in sorted(targets)})
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.key].append(event)
    instances: dict[str, Instance] = {}
    open_count = 0
    for key in sorted(grouped):
        ordered = evidence.ordered(grouped[key])
        instance = Instance(spec.name, key, ordered[0].partition, frozenset(spec.terminal))
        instances[key] = instance
        subject = f"{spec.name} {key}"
        for event in ordered:
            reasons: list[tuple[FindingVerdict, str]] = []
            if event.owner != spec.owner:
                reasons.append(("violated", f"recorded by {event.owner}, but {spec.owner} owns {spec.name}"))
            required = spec.required.get(event.target_state or "", ())
            reasons.extend(fact_problems(spec.facts, required, event.facts, spec.allowed))
            if event.partition != instance.partition:
                reasons.append(("violated", f"moved from partition {instance.partition} to {event.partition}"))
            target = event.target_state or ""
            move = edge(event.source_state, target)
            if instance.settled:
                reasons.append(("violated", f"changed after settling in {instance.current}: {move}"))
            elif event.source_state != instance.current:
                gap = not evidence.source(event.source).complete
                expected = instance.current or "its creation"
                reasons.append(("inconclusive" if gap else "violated", f"recorded {move} after {expected}"))
            if spec.allows(event.source_state, target):
                if move in counts:
                    counts[move] += 1
            elif not instance.settled:
                reasons.append(("violated", f"undeclared transition {move}"))
            findings.extend(_finding(verdict, subject, reason, event) for verdict, reason in reasons)
            facts = declared_facts(spec.facts, event.facts)
            instance.reached.append(Reached(instance.current, target, {**instance.facts, **facts}, event))
            instance.current = target
            instance.facts.update(facts)
        if not instance.settled and spec.terminal:
            last = evidence.source(ordered[-1].source)
            if spec.settles_at(last.closed, last.final):
                reason = f"still {instance.current} when {last.id} closed{' for good' if last.final else ''}"
                findings.append(_finding("violated", subject, reason, ordered[-1]))
            else:
                open_count += 1
    result = RuleResult(
        rule=f"machine:{spec.name}",
        kind="machine",
        summary=spec.summary,
        triggered=len(instances),
        open=open_count,
        findings=tuple(findings),
    )
    return instances, result, counts


def replay_boundary(
    spec: BoundarySpec, events: list[Event], evidence: Evidence
) -> tuple[dict[str, Exchange], RuleResult, dict[str, int]]:
    findings: list[Finding] = []
    counts = dict.fromkeys(spec.messages, 0)
    counts["abandoned"] = 0
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.key].append(event)
    exchanges: dict[str, Exchange] = {}
    open_count = 0
    for key in sorted(grouped):
        ordered = evidence.ordered(grouped[key])
        exchange = Exchange(key, ordered[0].partition, ordered)
        exchanges[key] = exchange
        subject = f"{spec.name} {key}"

        def violation(
            reason: str, *events: Event, subject: str = subject, verdict: FindingVerdict = "violated"
        ) -> None:
            findings.append(_finding(verdict, subject, reason, *events))

        for event in ordered:
            label = "abandoned" if event.kind == "abandon" else event.message or ""
            counts[label] = counts.get(label, 0) + 1
            if event.owner != spec.sender:
                violation(f"recorded by {event.owner}, but {spec.sender} sends {spec.name}", event)
            if event.kind == "send" and event.message != spec.request:
                violation(f"sent {event.message}, which is not the request", event)
            if event.kind == "receive" and event.message not in spec.responses:
                violation(f"received {event.message}, which is not a response", event)
            if event.kind != "abandon":
                message = event.message or ""
                declared, required = spec.facts.get(message, {}), spec.required.get(message, ())
                allowed = spec.allowed.get(message, {})
                for verdict, problem in fact_problems(declared, required, event.facts, allowed):
                    violation(problem, event, verdict=verdict)
        sends = [event for event in ordered if event.kind == "send"]
        outcomes = [event for event in ordered if event.kind in {"receive", "abandon"}]
        if not sends:
            violation("an outcome was recorded without a request", *outcomes)
        elif len(sends) > 1:
            violation(f"the request was sent {len(sends)} times", *sends)
        if len(outcomes) > 1:
            violation(f"{len(outcomes)} outcomes for one request", *outcomes)
        if sends and outcomes and ordered.index(outcomes[0]) < ordered.index(sends[0]):
            violation("the outcome was recorded before the request", outcomes[0], sends[0])
        if sends and not outcomes:
            last = evidence.source(sends[-1].source)
            if last.closed:
                violation(f"no outcome before {last.id} closed", sends[-1])
            else:
                open_count += 1
    result = RuleResult(
        rule=f"boundary:{spec.name}",
        kind="boundary",
        summary=spec.summary,
        triggered=len(exchanges),
        open=open_count,
        findings=tuple(findings),
    )
    return exchanges, result, counts


# ================================================
# Model: replayed evidence with order and coverage
# ================================================


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
                self.miscited[boundary].append(_finding("violated", subject, reason, citing, *candidates.values()))
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

    def occurrences(self, invariant: Invariant) -> list[Occurrence]:
        when = invariant.when
        if isinstance(when, EntityTrigger):
            return [
                Occurrence(
                    f"{when.entity} {instance.key}",
                    instance.key,
                    instance.partition,
                    reached.facts,
                    reached.event,
                    instance,
                    index,
                )
                for instance in self.instances.get(when.entity, {}).values()
                for index, reached in enumerate(instance.reached)
                if reached.state in when.to
                and (not when.source or (reached.source_state or CREATED) in when.source)
                and matches(when.where, reached.facts)
            ]
        return [
            Occurrence(
                f"{when.boundary}.{when.message} {exchange.key}",
                exchange.key,
                exchange.partition,
                event.facts,
                event,
            )
            for exchange in self.exchanges.get(when.boundary, {}).values()
            for event in exchange.events
            if event.message == when.message and matches(when.where, event.facts)
        ]


# ================================================
# Invariant patterns
# ================================================


def _ordered_requirement(model: Model, candidates: list[Event], occurrence: Occurrence, name: str) -> Finding | None:
    orders = [model.precedes(candidate, occurrence.event) for candidate in candidates]
    if any(order is True for order in orders):
        return None
    if all(order is False for order in orders):
        return _finding("violated", occurrence.subject, f"{name} happened only after it", occurrence.event, *candidates)
    reason = f"the evidence cannot order {name} against it"
    return _finding("inconclusive", occurrence.subject, reason, occurrence.event, *candidates)


def check_requires(
    model: Model, require: EntityRequirement | MessageRequirement, occurrence: Occurrence
) -> Finding | None:
    key = occurrence.key if require.key_from == OWN_KEY else occurrence.facts.get(require.key_from)
    if not isinstance(key, str) or not key:
        return _finding("violated", occurrence.subject, f"has no {require.key_from}", occurrence.event)
    # Only a requirement that precedes the trigger must be in a snapshot taken after it.
    before = occurrence.event if require.order == "before" else None
    if isinstance(require, EntityRequirement):
        target_spec = model.spec.entities[require.entity]
        instance = model.instances.get(require.entity, {}).get(key)
        name = f"{require.entity} {key}"
        if instance is None:
            certain, why = model.coverage(target_spec.owner, target_spec.evidence, occurrence.partition, before)
            if certain:
                return _finding("violated", occurrence.subject, f"{name} was never recorded", occurrence.event)
            return _finding("inconclusive", occurrence.subject, why, occurrence.event)
        states = " or ".join(require.reached)
        reached = [item for item in instance.reached if item.state in require.reached]
        satisfying = [item for item in reached if matches(require.where, item.facts, occurrence.facts)]
        last = instance.reached[-1].event
        if satisfying:
            if require.order == "before":
                name = f"{name} reaching {states}"
                return _ordered_requirement(model, [item.event for item in satisfying], occurrence, name)
            return None
        if reached:
            # A fact the condition needs that the record lacks leaves it undecided, as for the machine.
            if missing := sorted(
                {fact for item in reached for fact in absent(require.where, item.facts, occurrence.facts)}
            ):
                reason = f"{name} reached {reached[-1].state} without {', '.join(missing)}"
                return _finding("inconclusive", occurrence.subject, reason, occurrence.event, last)
            facts = {fact: reached[-1].facts.get(fact) for fact in require.where}
            reason = f"{name} reached {reached[-1].state} with {facts}"
            return _finding("violated", occurrence.subject, reason, occurrence.event, last)
        how = "settled in" if instance.settled else "is still"
        if instance.settled:
            return _finding("violated", occurrence.subject, f"{name} {how} {instance.current}", occurrence.event, last)
        # Still open: a state it must have reached before the trigger is certainly missing when the
        # evidence covers everything that happened before the trigger, as for a record never written.
        if require.order == "before":
            certain, why = model.coverage(target_spec.owner, target_spec.evidence, occurrence.partition, before)
            if certain:
                reason = f"{name} {how} {instance.current}, not {states}"
                return _finding("violated", occurrence.subject, reason, occurrence.event, last)
        return _finding("inconclusive", occurrence.subject, f"{name} {how} {instance.current}", occurrence.event, last)
    boundary = model.spec.boundaries[require.boundary]
    exchange = model.exchanges.get(require.boundary, {}).get(key)
    carrying = exchange.carrying(require.message) if exchange is not None else []
    name = f"{require.boundary}.{require.message} {key}"
    if carrying:
        if require.order == "before":
            return _ordered_requirement(model, carrying, occurrence, name)
        return None
    certain, why = model.coverage(boundary.sender, "journal", occurrence.partition, before)
    if certain:
        return _finding("violated", occurrence.subject, f"no {name}", occurrence.event)
    return _finding("inconclusive", occurrence.subject, why, occurrence.event)


def check_response(model: Model, eventually: tuple[str, ...], occurrence: Occurrence) -> Finding | None:
    instance = occurrence.instance
    if instance is None:  # The specification only allows entity triggers here.
        return _finding("inconclusive", occurrence.subject, "not an entity transition", occurrence.event)
    later = instance.reached[occurrence.index + 1 :]
    if any(item.state in eventually for item in later):
        return None
    last = instance.reached[-1].event
    if instance.settled:
        return _finding("violated", occurrence.subject, f"settled in {instance.current}", occurrence.event, last)
    # "Eventually" has a horizon only where the owner's journal ended in a way that settles the entity:
    # after that, nothing can still bring the response.
    source = model.evidence.source(last.source)
    if model.spec.entities[instance.subject].settles_at(source.closed, source.final):
        reason = f"still {instance.current} when {source.id} closed{' for good' if source.final else ''}"
        return _finding("violated", occurrence.subject, reason, occurrence.event, last)
    return _finding("inconclusive", occurrence.subject, f"still {instance.current}", occurrence.event, last)


def check_guard(require: GuardRequirement, occurrence: Occurrence) -> Finding | None:
    if matches(require.where, occurrence.facts):
        return None
    reached = occurrence.instance.reached[occurrence.index] if occurrence.instance else None
    move = edge(reached.source_state, reached.state) if reached else "transition"
    if missing := absent(require.where, occurrence.facts):
        return _finding("inconclusive", occurrence.subject, f"{move} without {', '.join(missing)}", occurrence.event)
    facts = {name: occurrence.facts.get(name) for name in require.where}
    return _finding("violated", occurrence.subject, f"{move} with {facts}", occurrence.event)


def check_excludes(model: Model, require: ExclusionRequirement, occurrence: Occurrence) -> list[Finding]:
    findings: list[Finding] = []
    for instance in model.instances.get(require.entity, {}).values():
        if instance.partition != occurrence.partition:
            continue
        known, state = model.state_at(instance, occurrence.event)
        name = f"{require.entity} {instance.key}"
        if not known:
            reason = f"the evidence cannot order {name} against it"
            findings.append(_finding("inconclusive", occurrence.subject, reason, occurrence.event))
        elif state in require.in_states:
            findings.append(_finding("violated", occurrence.subject, f"{name} was {state}", occurrence.event))
    return findings


def judge(model: Model, invariant: Invariant, occurrence: Occurrence) -> list[Finding]:
    """What one occurrence of an invariant found; empty when it held."""
    require = invariant.require
    if isinstance(require, ExclusionRequirement):
        return check_excludes(model, require, occurrence)
    if isinstance(require, EntityRequirement | MessageRequirement):
        found = check_requires(model, require, occurrence)
    elif isinstance(require, GuardRequirement):
        found = check_guard(require, occurrence)
    else:
        found = check_response(model, invariant.eventually, occurrence)
    return [found] if found is not None else []


def check_invariant(model: Model, invariant: Invariant) -> RuleResult:
    occurrences = model.occurrences(invariant)
    findings = [finding for occurrence in occurrences for finding in judge(model, invariant, occurrence)]
    return RuleResult(
        rule=invariant.id,
        kind="invariant",
        summary=invariant.summary,
        triggered=len(occurrences),
        findings=tuple(findings),
    )


class Judgement(EvidenceModel):
    """One invariant occurrence and its verdict, addressed by the event that triggered it."""

    rule: str
    event: str  # Event.ref of the trigger; Git events of one commit share it.
    subject: str  # The trigger's entity or boundary, and its key: what tells such events apart.
    key: str
    verdict: Literal["passed", "violated", "inconclusive"]
    findings: tuple[Finding, ...] = ()


def judge_occurrences(model: Model) -> list[Judgement]:
    """Every invariant occurrence with its own verdict, so views can attach rules to the events they checked."""
    judgements: list[Judgement] = []
    for invariant in model.spec.invariants:
        for occurrence in model.occurrences(invariant):
            findings = judge(model, invariant, occurrence)
            verdict: Literal["passed", "violated", "inconclusive"] = (
                "violated"
                if any(finding.verdict == "violated" for finding in findings)
                else "inconclusive"
                if findings
                else "passed"
            )
            judgements.append(
                Judgement(
                    rule=invariant.id,
                    event=occurrence.event.ref,
                    subject=occurrence.event.subject,
                    key=occurrence.event.key,
                    verdict=verdict,
                    findings=tuple(findings),
                )
            )
    return judgements


# ================================================
# Evidence-level rules
# ================================================


def states_around(model: Model, instance: Instance, cut: Cut) -> set[str] | None:
    """The states a store snapshot taken at ``cut`` may hold for one instance.

    Owners write their store and then journal the change, so the snapshot holds
    the state at the cut's start, one reached while it was taken, or the first
    one journaled after it. None when the instance's journal shares no process with the cut.
    """
    states: set[str] = set()
    last: str | None = None
    for item in instance.reached:
        placed = model.placed(item.event, cut)
        if placed is None:
            return None
        if placed == "before":
            last = item.state
            continue
        states.add(item.state)
        if placed == "after":
            break
    if last is not None:
        states.add(last)
    return states


def check_reconciliation(model: Model, observed: list[Event]) -> RuleResult:
    """Persisted owner state must be what the owner's journal replays to.

    A store record the journal never mentions, or one that disagrees with the
    replayed state, means some code changed state without journaling it.
    """
    findings: list[Finding] = []
    for event in observed:
        spec = model.spec.entities.get(event.subject)
        subject = f"{event.subject} {event.key}"
        if spec is None:
            findings.append(_finding("violated", subject, "persisted for an undeclared entity", event))
            continue
        certain, why = model.coverage(spec.owner, spec.evidence, event.partition)
        verdict: FindingVerdict = "violated" if certain else "inconclusive"
        instance = model.instances.get(event.subject, {}).get(event.key)
        cut = model.evidence.source(event.source).cut
        if instance is None:
            reason = f"persisted as {event.target_state}, but never journaled" if certain else why
            findings.append(_finding(verdict, subject, reason, event))
        elif cut is not None:
            states = states_around(model, instance, cut)
            if states is None:
                reason = f"the evidence cannot place its journal against when {event.source} was taken"
                findings.append(_finding("inconclusive", subject, reason, event))
            elif event.target_state not in states:
                shown = sorted(states)
                reason = f"persisted as {event.target_state}, but around {event.source} the journal shows {shown}"
                findings.append(_finding(verdict, subject, reason, event, instance.reached[-1].event))
        elif instance.current != event.target_state:
            reason = f"persisted as {event.target_state}, but the journal replays to {instance.current}"
            findings.append(_finding(verdict, subject, reason, event, instance.reached[-1].event))
    return RuleResult(
        rule="reconciliation",
        kind="reconciliation",
        summary="Persisted owner state is exactly what the owner's journal replays to.",
        triggered=len(observed),
        findings=tuple(findings),
    )


def check_evidence(spec: Spec, evidence: Evidence) -> RuleResult:
    findings = [Finding(verdict="inconclusive", subject="evidence", reason=problem) for problem in evidence.problems]
    for source in evidence.sources:
        findings.extend(
            Finding(verdict="inconclusive", subject=source.id, reason=problem) for problem in source.problems
        )
        # A process the vocabulary places nothing in is the owner's own, like any undeclared subject.
        expected_hosts = spec.hosted_by(source.process)
        if source.kind == "journal" and expected_hosts and source.hosts != expected_hosts:
            findings.append(
                Finding(
                    verdict="inconclusive",
                    subject=source.id,
                    reason=f"journal speaks for {sorted(source.hosts)}, the specification places "
                    f"{sorted(expected_hosts)} in process {source.process}",
                )
            )
    return RuleResult(
        rule="evidence",
        kind="evidence",
        summary="Sources are complete and readable, and journals speak for the components the specification "
        "places in their process.",
        triggered=len(evidence.sources),
        findings=tuple(findings),
    )


def extras(spec: Spec, evidence: Evidence) -> tuple[Extra, ...]:
    """What the evidence holds beyond the vocabulary, for the report; never part of a verdict."""
    found: dict[tuple[str, str | None], list[Event]] = defaultdict(list)
    for event in evidence.events:
        if event.kind == "observed":
            continue
        if event.subject in spec.entities:
            declared = spec.entities[event.subject].facts
        elif event.subject in spec.boundaries and event.kind != "abandon":
            declared = spec.boundaries[event.subject].facts.get(event.message or "", {})
        elif event.subject in spec.boundaries:
            continue
        else:
            found[(event.subject, None)].append(event)
            continue
        for fact in event.facts:
            if fact not in declared:
                found[(event.subject, fact)].append(event)
    return tuple(
        Extra(subject=subject, fact=fact, count=len(events), evidence=tuple(event.ref for event in events[:3]))
        for (subject, fact), events in sorted(found.items(), key=lambda item: (item[0][0], item[0][1] or ""))
    )


def _by_subject(events: tuple[Event, ...]) -> dict[str, list[Event]]:
    grouped: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        grouped[event.subject].append(event)
    return grouped


def replay(spec: Spec, evidence: Evidence) -> tuple[Model, list[RuleResult], Coverage]:
    """Replay every entity and boundary; the model the invariants and views are evaluated on."""
    by_subject = _by_subject(evidence.events)
    rules: list[RuleResult] = []
    instances: dict[str, dict[str, Instance]] = {}
    exchanges: dict[str, dict[str, Exchange]] = {}
    transitions: dict[str, dict[str, int]] = {}
    messages: dict[str, dict[str, int]] = {}
    for name, entity in sorted(spec.entities.items()):
        events = [event for event in by_subject.get(name, []) if event.kind == "transition"]
        stray = [event for event in by_subject.get(name, []) if event.kind not in {"transition", "observed"}]
        instances[name], result, transitions[name] = replay_entity(entity, events, evidence)
        if stray:
            stray_finding = _finding("violated", name, "messages recorded against an entity", *stray[:3])
            result = result.model_copy(update={"findings": (*result.findings, stray_finding)})
        rules.append(result)
    for name, boundary in sorted(spec.boundaries.items()):
        events = [event for event in by_subject.get(name, []) if event.kind in {"send", "receive", "abandon"}]
        stray = [event for event in by_subject.get(name, []) if event.kind not in {"send", "receive", "abandon"}]
        exchanges[name], result, messages[name] = replay_boundary(boundary, events, evidence)
        if stray:
            stray_finding = _finding("violated", name, "transitions recorded against a boundary", *stray[:3])
            result = result.model_copy(update={"findings": (*result.findings, stray_finding)})
        rules.append(result)
    model = Model(spec, evidence, instances, exchanges)
    rules = [
        rule.model_copy(update={"findings": (*rule.findings, *model.miscited[rule.rule.removeprefix("boundary:")])})
        if rule.kind == "boundary"
        else rule
        for rule in rules
    ]
    return model, rules, Coverage(transitions=transitions, messages=messages)


def check(spec: Spec, evidence: Evidence) -> CheckResult:
    model, replayed, coverage = replay(spec, evidence)
    rules = [check_evidence(spec, evidence), *replayed]
    rules.extend(check_invariant(model, invariant) for invariant in spec.invariants)
    observed = [event for event in evidence.events if event.kind == "observed"]
    if observed:
        rules.append(check_reconciliation(model, observed))
    return CheckResult(
        spec_digest=spec.digest,
        vocabulary_digest=spec.vocabulary_digest,
        sources=evidence.sources,
        rules=tuple(rules),
        coverage=coverage,
        extras=extras(spec, evidence),
    )


__all__ = [
    "CheckResult",
    "Coverage",
    "Extra",
    "Finding",
    "Judgement",
    "Model",
    "RuleResult",
    "check",
    "judge_occurrences",
    "replay",
]
