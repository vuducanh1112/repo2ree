"""Check evidence against the specification; the same inputs always give the same verdicts.

Absence is a violation only where a complete source covering the subject could
have recorded it, and order is asserted only where the evidence establishes it.
Everything else that cannot be decided is inconclusive, never a pass.

Order comes from three places only: positions within one source, epochs and
positions within one process's journals, and boundary exchanges that bracket
the receiver's work (``brackets`` in a boundary spec). Wall-clock time is never
used.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue

from repo2ree_conformance.evidence import Event, Evidence, EvidenceModel, Source
from repo2ree_conformance.spec import (
    CREATED,
    OWN_KEY,
    BoundarySpec,
    EntityRequirement,
    EntitySpec,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    Spec,
    fact_problem,
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


class Coverage(EvidenceModel):
    """How often each declared edge and message was observed; zero marks a gap."""

    transitions: dict[str, dict[str, int]]
    messages: dict[str, dict[str, int]]


class CheckResult(EvidenceModel):
    spec_digest: str
    sources: tuple[Source, ...]
    rules: tuple[RuleResult, ...]
    coverage: Coverage

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
    counts: dict[str, int] = {edge(None, state): 0 for state in spec.initial}
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
            if problem := fact_problem(spec.facts, event.facts):
                reasons.append(("violated", problem))
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
                counts[move] += 1
            elif not instance.settled:
                reasons.append(("violated", f"undeclared transition {move}"))
            findings.extend(_finding(verdict, subject, reason, event) for verdict, reason in reasons)
            instance.reached.append(Reached(instance.current, target, {**instance.facts, **event.facts}, event))
            instance.current = target
            instance.facts.update(event.facts)
        if not instance.settled and spec.terminal:
            last = evidence.source(ordered[-1].source)
            if spec.settles_before_close and last.closed:
                reason = f"still {instance.current} when {last.id} closed"
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

        def violation(reason: str, *events: Event, subject: str = subject) -> None:
            findings.append(_finding("violated", subject, reason, *events))

        for event in ordered:
            label = "abandoned" if event.kind == "abandon" else event.message or ""
            counts[label] = counts.get(label, 0) + 1
            if event.owner != spec.sender:
                violation(f"recorded by {event.owner}, but {spec.sender} sends {spec.name}", event)
            if event.kind == "send" and event.message != spec.request:
                violation(f"sent {event.message}, which is not the request", event)
            if event.kind == "receive" and event.message not in spec.responses:
                violation(f"received {event.message}, which is not a response", event)
            if event.kind != "abandon" and (
                problem := fact_problem(spec.facts.get(event.message or "", {}), event.facts)
            ):
                violation(problem, event)
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

    def coverage(self, owner: str, kind: str, partition: str | None) -> tuple[bool, str]:
        """Whether a missing record is certain: (complete coverage, explanation)."""
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
        return True, ""

    def _direct(self, a: Event, b: Event) -> bool | None:
        if a.source == b.source:
            return a.position < b.position
        first, second = self._sources[a.source], self._sources[b.source]
        if first.kind == second.kind == "journal" and first.process == second.process:
            return (first.rank, a.position) < (second.rank, b.position)
        return None

    def _bracket(self, event: Event) -> tuple[Event, Event | None] | None:
        if event.kind != "transition":
            return None
        boundary = self.spec.bracketing(event.subject)
        exchange = self.exchanges.get(boundary.name, {}).get(event.key) if boundary is not None else None
        if exchange is None or exchange.request is None:
            return None
        return exchange.request, exchange.outcome

    def precedes(self, a: Event, b: Event) -> bool | None:
        """True if ``a`` happened before ``b``, False if after, None if the evidence cannot say."""
        if a is b:
            return False
        if (direct := self._direct(a, b)) is not None:
            return direct
        if bracket := self._bracket(a):
            request, outcome = bracket
            if outcome is not None and (outcome is b or self._direct(outcome, b)):
                return True
            if self._direct(b, request):
                return False
        if bracket := self._bracket(b):
            request, outcome = bracket
            if request is a or self._direct(a, request):
                return True
            if outcome is not None and self._direct(outcome, a):
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
    if isinstance(require, EntityRequirement):
        target_spec = model.spec.entities[require.entity]
        instance = model.instances.get(require.entity, {}).get(key)
        name = f"{require.entity} {key}"
        if instance is None:
            certain, why = model.coverage(target_spec.owner, target_spec.evidence, occurrence.partition)
            if certain:
                return _finding("violated", occurrence.subject, f"{name} was never recorded", occurrence.event)
            return _finding("inconclusive", occurrence.subject, why, occurrence.event)
        reached = [item for item in instance.reached if item.state == require.reached]
        satisfying = [item for item in reached if matches(require.where, item.facts)]
        last = instance.reached[-1].event
        if satisfying:
            if require.order == "before":
                name = f"{name} reaching {require.reached}"
                return _ordered_requirement(model, [item.event for item in satisfying], occurrence, name)
            return None
        if reached:
            facts = {fact: reached[-1].facts.get(fact) for fact in require.where}
            reason = f"{name} reached {require.reached} with {facts}"
            return _finding("violated", occurrence.subject, reason, occurrence.event, last)
        verdict: FindingVerdict = "violated" if instance.settled else "inconclusive"
        how = "settled in" if instance.settled else "is still"
        return _finding(verdict, occurrence.subject, f"{name} {how} {instance.current}", occurrence.event, last)
    boundary = model.spec.boundaries[require.boundary]
    exchange = model.exchanges.get(require.boundary, {}).get(key)
    carrying = exchange.carrying(require.message) if exchange is not None else []
    name = f"{require.boundary}.{require.message} {key}"
    if carrying:
        if require.order == "before":
            return _ordered_requirement(model, carrying, occurrence, name)
        return None
    certain, why = model.coverage(boundary.sender, "journal", occurrence.partition)
    if certain:
        return _finding("violated", occurrence.subject, f"no {name}", occurrence.event)
    return _finding("inconclusive", occurrence.subject, why, occurrence.event)


def check_response(eventually: tuple[str, ...], occurrence: Occurrence) -> Finding | None:
    instance = occurrence.instance
    if instance is None:  # The specification only allows entity triggers here.
        return _finding("inconclusive", occurrence.subject, "not an entity transition", occurrence.event)
    later = instance.reached[occurrence.index + 1 :]
    if any(item.state in eventually for item in later):
        return None
    last = instance.reached[-1].event
    if instance.settled:
        return _finding("violated", occurrence.subject, f"settled in {instance.current}", occurrence.event, last)
    return _finding("inconclusive", occurrence.subject, f"still {instance.current}", occurrence.event, last)


def check_guard(require: GuardRequirement, occurrence: Occurrence) -> Finding | None:
    if matches(require.where, occurrence.facts):
        return None
    reached = occurrence.instance.reached[occurrence.index] if occurrence.instance else None
    move = edge(reached.source_state, reached.state) if reached else "transition"
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


def check_invariant(model: Model, invariant: Invariant) -> RuleResult:
    occurrences = model.occurrences(invariant)
    require = invariant.require
    findings: list[Finding] = []
    for occurrence in occurrences:
        if isinstance(require, ExclusionRequirement):
            findings.extend(check_excludes(model, require, occurrence))
            continue
        if isinstance(require, EntityRequirement | MessageRequirement):
            found = check_requires(model, require, occurrence)
        elif isinstance(require, GuardRequirement):
            found = check_guard(require, occurrence)
        else:
            found = check_response(invariant.eventually, occurrence)
        if found is not None:
            findings.append(found)
    return RuleResult(
        rule=invariant.id,
        kind="invariant",
        summary=invariant.summary,
        triggered=len(occurrences),
        findings=tuple(findings),
    )


# ================================================
# Evidence-level rules
# ================================================


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
        if instance is None:
            reason = f"persisted as {event.target_state}, but never journaled" if certain else why
            findings.append(_finding(verdict, subject, reason, event))
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
        expected_hosts = spec.hosted_by(source.process)
        if source.kind == "journal" and source.hosts != expected_hosts:
            findings.append(
                Finding(
                    verdict="inconclusive",
                    subject=source.id,
                    reason=f"journal speaks for {sorted(source.hosts)}, the specification places "
                    f"{sorted(expected_hosts)} in process {source.process}",
                )
            )
        if source.spec_digest is not None and source.spec_digest != spec.digest:
            findings.append(
                Finding(
                    verdict="inconclusive",
                    subject=source.id,
                    reason=f"written against specification {source.spec_digest}, checking {spec.digest}",
                )
            )
    known_subjects = {*spec.entities, *spec.boundaries}
    for subject, events in sorted(_by_subject(evidence.events).items()):
        if subject not in known_subjects:
            findings.append(
                Finding(
                    verdict="violated",
                    subject=subject,
                    reason=f"{len(events)} events for an undeclared entity or boundary",
                    evidence=tuple(event.ref for event in events[:3]),
                )
            )
    return RuleResult(
        rule="evidence",
        kind="evidence",
        summary="Sources are complete, readable, and written against this specification.",
        triggered=len(evidence.sources),
        findings=tuple(findings),
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
        exchanges[name], result, messages[name] = replay_boundary(boundary, events, evidence)
        rules.append(result)
    return (
        Model(spec, evidence, instances, exchanges),
        rules,
        Coverage(transitions=transitions, messages=messages),
    )


def check(spec: Spec, evidence: Evidence) -> CheckResult:
    model, replayed, coverage = replay(spec, evidence)
    rules = [check_evidence(spec, evidence), *replayed]
    rules.extend(check_invariant(model, invariant) for invariant in spec.invariants)
    observed = [event for event in evidence.events if event.kind == "observed"]
    if observed:
        rules.append(check_reconciliation(model, observed))
    return CheckResult(spec_digest=spec.digest, sources=evidence.sources, rules=tuple(rules), coverage=coverage)


__all__ = ["CheckResult", "Coverage", "Finding", "Model", "RuleResult", "check", "replay"]
