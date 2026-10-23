"""Persisted owner state against what the owner's journal replays to."""

from __future__ import annotations

from repo2ree_assurance_checker.check.order import Model
from repo2ree_assurance_checker.check.replay import Instance
from repo2ree_assurance_checker.check.results import (
    Finding,
    FindingVerdict,
    RuleResult,
    finding,
)
from repo2ree_assurance_checker.evidence import Cut, Event


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
            findings.append(finding("violated", subject, "persisted for an undeclared entity", event))
            continue
        certain, why = model.coverage(spec.owner, spec.evidence, event.partition)
        verdict: FindingVerdict = "violated" if certain else "inconclusive"
        instance = model.instances.get(event.subject, {}).get(event.key)
        cut = model.evidence.source(event.source).cut
        if instance is None:
            reason = f"persisted as {event.target_state}, but never journaled" if certain else why
            findings.append(finding(verdict, subject, reason, event))
        elif cut is not None:
            states = states_around(model, instance, cut)
            if states is None:
                reason = f"the evidence cannot place its journal against when {event.source} was taken"
                findings.append(finding("inconclusive", subject, reason, event))
            elif event.target_state not in states:
                shown = sorted(states)
                reason = f"persisted as {event.target_state}, but around {event.source} the journal shows {shown}"
                findings.append(finding(verdict, subject, reason, event, instance.reached[-1].event))
        elif instance.current != event.target_state:
            reason = f"persisted as {event.target_state}, but the journal replays to {instance.current}"
            findings.append(finding(verdict, subject, reason, event, instance.reached[-1].event))
    return RuleResult(
        rule="reconciliation",
        kind="reconciliation",
        summary="Persisted owner state is exactly what the owner's journal replays to.",
        triggered=len(observed),
        findings=tuple(findings),
    )
