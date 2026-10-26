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

The package is laid out by concern: ``results`` (what checking finds), ``replay`` (records
through machines and exchanges), ``order`` (what the evidence can order and could have
recorded), ``patterns`` (the invariants), ``reconciliation`` (stores against journals), and
``aggregates`` (every part of a committed document, reported apart from the verdict).
"""

from __future__ import annotations

from collections import defaultdict

from repo2ree_assurance_checker.check.aggregates import check_aggregates
from repo2ree_assurance_checker.check.order import Model
from repo2ree_assurance_checker.check.patterns import Occurrence, check_invariant, judge, judge_occurrences, occurrences
from repo2ree_assurance_checker.check.reconciliation import check_reconciliation, states_around
from repo2ree_assurance_checker.check.replay import Exchange, Instance, Reached, replay_boundary, replay_entity
from repo2ree_assurance_checker.check.results import (
    INITIAL,
    AggregateResult,
    CheckResult,
    Coverage,
    Extra,
    Finding,
    Judgement,
    MoveCount,
    RuleResult,
    finding,
)
from repo2ree_assurance_checker.evidence import Event, Evidence
from repo2ree_assurance_checker.spec import Spec


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
            stray_finding = finding("violated", name, "messages recorded against an entity", *stray[:3])
            result = result.model_copy(update={"findings": (*result.findings, stray_finding)})
        rules.append(result)
    for name, boundary in sorted(spec.boundaries.items()):
        events = [event for event in by_subject.get(name, []) if event.kind in {"send", "receive", "abandon"}]
        stray = [event for event in by_subject.get(name, []) if event.kind not in {"send", "receive", "abandon"}]
        exchanges[name], result, messages[name] = replay_boundary(boundary, events, evidence)
        if stray:
            stray_finding = finding("violated", name, "transitions recorded against a boundary", *stray[:3])
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
        aggregates=check_aggregates(spec, evidence),
    )


__all__ = [
    "INITIAL",
    "AggregateResult",
    "CheckResult",
    "Coverage",
    "Exchange",
    "Extra",
    "Finding",
    "Instance",
    "Judgement",
    "Model",
    "MoveCount",
    "Occurrence",
    "Reached",
    "RuleResult",
    "check",
    "check_aggregates",
    "check_invariant",
    "check_reconciliation",
    "judge",
    "judge_occurrences",
    "occurrences",
    "replay",
    "states_around",
]
