"""The invariant patterns: each occurrence of a trigger, and what its requirement found."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from repo2ree_assurance_checker.check.order import Model
from repo2ree_assurance_checker.check.replay import Instance
from repo2ree_assurance_checker.check.results import (
    Finding,
    Judgement,
    RuleResult,
    edge,
    finding,
)
from repo2ree_assurance_checker.evidence import Event
from repo2ree_assurance_checker.spec import (
    CREATED,
    OWN_KEY,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    absent,
    matches,
)


@dataclass
class Occurrence:
    subject: str
    key: str
    partition: str | None
    facts: dict[str, JsonValue]
    event: Event
    instance: Instance | None = None
    index: int = 0


def occurrences(model: Model, invariant: Invariant) -> list[Occurrence]:
    """Every event that triggers ``invariant``, with what judging it needs."""
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
            for instance in model.instances.get(when.entity, {}).values()
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
        for exchange in model.exchanges.get(when.boundary, {}).values()
        for event in exchange.events
        if event.message == when.message and matches(when.where, event.facts)
    ]


def _ordered_requirement(model: Model, candidates: list[Event], occurrence: Occurrence, name: str) -> Finding | None:
    orders = [model.precedes(candidate, occurrence.event) for candidate in candidates]
    if any(order is True for order in orders):
        return None
    if all(order is False for order in orders):
        return finding("violated", occurrence.subject, f"{name} happened only after it", occurrence.event, *candidates)
    reason = f"the evidence cannot order {name} against it"
    return finding("inconclusive", occurrence.subject, reason, occurrence.event, *candidates)


def check_requires(
    model: Model, require: EntityRequirement | MessageRequirement, occurrence: Occurrence
) -> Finding | None:
    key = occurrence.key if require.key_from == OWN_KEY else occurrence.facts.get(require.key_from)
    if not isinstance(key, str) or not key:
        return finding("violated", occurrence.subject, f"has no {require.key_from}", occurrence.event)
    # Only a requirement that precedes the trigger must be in a snapshot taken after it.
    before = occurrence.event if require.order == "before" else None
    if isinstance(require, EntityRequirement):
        target_spec = model.spec.entities[require.entity]
        instance = model.instances.get(require.entity, {}).get(key)
        name = f"{require.entity} {key}"
        if instance is None:
            certain, why = model.coverage(target_spec.owner, target_spec.evidence, occurrence.partition, before)
            if certain:
                return finding("violated", occurrence.subject, f"{name} was never recorded", occurrence.event)
            return finding("inconclusive", occurrence.subject, why, occurrence.event)
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
                return finding("inconclusive", occurrence.subject, reason, occurrence.event, last)
            facts = {fact: reached[-1].facts.get(fact) for fact in require.where}
            reason = f"{name} reached {reached[-1].state} with {facts}"
            return finding("violated", occurrence.subject, reason, occurrence.event, last)
        how = "settled in" if instance.settled else "is still"
        if instance.settled:
            return finding("violated", occurrence.subject, f"{name} {how} {instance.current}", occurrence.event, last)
        # Still open: a state it must have reached before the trigger is certainly missing when the
        # evidence covers everything that happened before the trigger, as for a record never written.
        if require.order == "before":
            certain, why = model.coverage(target_spec.owner, target_spec.evidence, occurrence.partition, before)
            if certain:
                reason = f"{name} {how} {instance.current}, not {states}"
                return finding("violated", occurrence.subject, reason, occurrence.event, last)
        return finding("inconclusive", occurrence.subject, f"{name} {how} {instance.current}", occurrence.event, last)
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
        return finding("violated", occurrence.subject, f"no {name}", occurrence.event)
    return finding("inconclusive", occurrence.subject, why, occurrence.event)


def check_response(model: Model, eventually: tuple[str, ...], occurrence: Occurrence) -> Finding | None:
    instance = occurrence.instance
    if instance is None:  # The specification only allows entity triggers here.
        return finding("inconclusive", occurrence.subject, "not an entity transition", occurrence.event)
    later = instance.reached[occurrence.index + 1 :]
    if any(item.state in eventually for item in later):
        return None
    last = instance.reached[-1].event
    if instance.settled:
        return finding("violated", occurrence.subject, f"settled in {instance.current}", occurrence.event, last)
    # "Eventually" has a horizon only where the owner's journal ended in a way that settles the entity:
    # after that, nothing can still bring the response.
    source = model.evidence.source(last.source)
    if model.spec.entities[instance.subject].settles_at(source.closed, source.final):
        reason = f"still {instance.current} when {source.id} closed{' for good' if source.final else ''}"
        return finding("violated", occurrence.subject, reason, occurrence.event, last)
    return finding("inconclusive", occurrence.subject, f"still {instance.current}", occurrence.event, last)


def check_guard(require: GuardRequirement, occurrence: Occurrence) -> Finding | None:
    if matches(require.where, occurrence.facts):
        return None
    reached = occurrence.instance.reached[occurrence.index] if occurrence.instance else None
    move = edge(reached.source_state, reached.state) if reached else "transition"
    if missing := absent(require.where, occurrence.facts):
        return finding("inconclusive", occurrence.subject, f"{move} without {', '.join(missing)}", occurrence.event)
    facts = {name: occurrence.facts.get(name) for name in require.where}
    return finding("violated", occurrence.subject, f"{move} with {facts}", occurrence.event)


def check_excludes(model: Model, require: ExclusionRequirement, occurrence: Occurrence) -> list[Finding]:
    findings: list[Finding] = []
    for instance in model.instances.get(require.entity, {}).values():
        if instance.partition != occurrence.partition:
            continue
        known, state = model.state_at(instance, occurrence.event)
        name = f"{require.entity} {instance.key}"
        if not known:
            reason = f"the evidence cannot order {name} against it"
            findings.append(finding("inconclusive", occurrence.subject, reason, occurrence.event))
        elif state in require.in_states:
            findings.append(finding("violated", occurrence.subject, f"{name} was {state}", occurrence.event))
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
    triggered = occurrences(model, invariant)
    findings = [found for occurrence in triggered for found in judge(model, invariant, occurrence)]
    return RuleResult(
        rule=invariant.id,
        kind="invariant",
        summary=invariant.summary,
        triggered=len(triggered),
        findings=tuple(findings),
    )


def judge_occurrences(model: Model) -> list[Judgement]:
    """Every invariant occurrence with its own verdict, so views can attach rules to the events they checked."""
    judgements: list[Judgement] = []
    for invariant in model.spec.invariants:
        for occurrence in occurrences(model, invariant):
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
