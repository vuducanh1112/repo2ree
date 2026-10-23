"""Replay: each entity's records through its machine and each exchange's messages, with what broke the rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import JsonValue

from repo2ree_assurance_checker.check.results import (
    Finding,
    FindingVerdict,
    RuleResult,
    edge,
    finding,
)
from repo2ree_assurance_checker.evidence import Event, Evidence
from repo2ree_assurance_checker.spec import (
    BoundarySpec,
    EntitySpec,
    declared_facts,
    fact_problems,
)


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
            findings.extend(finding(verdict, subject, reason, event) for verdict, reason in reasons)
            facts = declared_facts(spec.facts, event.facts)
            instance.reached.append(Reached(instance.current, target, {**instance.facts, **facts}, event))
            instance.current = target
            instance.facts.update(facts)
        if not instance.settled and spec.terminal:
            last = evidence.source(ordered[-1].source)
            if spec.settles_at(last.closed, last.final):
                reason = f"still {instance.current} when {last.id} closed{' for good' if last.final else ''}"
                findings.append(finding("violated", subject, reason, ordered[-1]))
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
            findings.append(finding(verdict, subject, reason, *events))

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
