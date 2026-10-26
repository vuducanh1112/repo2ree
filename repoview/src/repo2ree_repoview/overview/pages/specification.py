"""What the checker holds the evidence to: machines, citations, invariants, and listed values."""

from __future__ import annotations

import json
from collections import defaultdict

from repo2ree_repoview.overview.drawing import machine_svg, system_svg
from repo2ree_repoview.overview.exports import (
    Condition,
    Conditions,
    EntityRequirement,
    EntitySide,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    MessageTrigger,
    NotEqual,
    OneOf,
    PerFact,
    Scalar,
    Spec,
)
from repo2ree_repoview.overview.html import Page, esc, rule_link, section, table
from repo2ree_repoview.overview.pages.aggregate import without_machine


def literal(value: Scalar) -> str:
    """A condition's value as written in the specification: names bare, anything else (``""``, ``false``) as JSON."""
    return value if isinstance(value, str) and value else json.dumps(value)


type Groups = dict[str, dict[str, tuple[str, ...]]]


def whole_groups(values: tuple[Scalar, ...], groups: dict[str, tuple[str, ...]]) -> list[str]:
    """The groups that together list exactly ``values``, in declaration order; none when no such groups exist."""
    named = [group for group, members in groups.items() if set(members) <= set(values)]
    covered = {value for group in named for value in groups[group]}
    return named if covered == set(values) else []


def condition(name: str, value: Condition, groups: Groups) -> str:
    """A condition as the specification states it: a value list that is whole groups reads as those groups."""
    match value:
        case NotEqual(value=excluded):
            return f"{name} ≠ {literal(excluded)}"
        case PerFact(fact=fact, cases=cases):
            # The alternatives depend on the trigger's fact: one list for each of its values.
            listed = "; ".join(f"{key}: {', '.join(map(literal, items))}" for key, items in cases.items())
            return f"{name} by the trigger's {fact} ({listed})"
        case OneOf(values=values):
            if named := whole_groups(values, groups.get(name, {})):
                return f"{name} ∈ {' ∪ '.join(named)}"  # noqa: RUF001 — the union sign, as the page shows it
            return f"{name} ∈ {{{', '.join(map(literal, values))}}}"
        case _:
            return f"{name} = {literal(value)}"


def where(conditions: Conditions, groups: Groups) -> str:
    if not conditions:
        return ""
    return " where " + ", ".join(condition(name, value, groups) for name, value in conditions.items())


def entity_groups(spec: Spec, entity: str) -> Groups:
    return spec.entities[entity].groups if entity in spec.entities else {}


def trigger_text(spec: Spec, invariant: Invariant) -> str:
    match invariant.when:
        case EntityTrigger() as when:
            source = f" from {' | '.join(when.source)}" if when.source else ""
            conditions = where(when.where, entity_groups(spec, when.entity))
            return f"{when.entity}{source} → {' | '.join(when.to)}{conditions}"
        case MessageTrigger() as when:
            return f"{when.boundary}.{when.message}{where(when.where, {})}"


def keyed(key_from: str) -> str:
    return "its own key" if key_from == "$key" else key_from


def requirement_text(spec: Spec, invariant: Invariant) -> str:
    match invariant.require:
        case None:
            return f"eventually {' | '.join(invariant.eventually)}"
        case GuardRequirement() as guard:
            trigger = invariant.when.entity if isinstance(invariant.when, EntityTrigger) else ""
            return where(guard.where, entity_groups(spec, trigger)).removeprefix(" where ")
        case ExclusionRequirement() as exclusion:
            partition = spec.entities[exclusion.entity].partition
            return f"no {exclusion.entity} in {' | '.join(exclusion.in_states)} with the same {partition}"
        case EntityRequirement() as require:
            before = ", before it" if require.order == "before" else ""
            conditions = where(require.where, entity_groups(spec, require.entity))
            reached = " | ".join(require.reached)
            return f"{require.entity} keyed by {keyed(require.key_from)} reached {reached}{conditions}{before}"
        case MessageRequirement() as require:
            before = ", before it" if require.order == "before" else ""
            return f"{require.boundary}.{require.message} keyed by {keyed(require.key_from)} was recorded{before}"


def rule_values(spec: Spec) -> tuple[dict[tuple[str, str, Scalar], list[str]], dict[str, list[str]]]:
    """((entity, fact, value) -> the rules whose trigger names that value, entity -> the rules naming none of its).

    A requirement's conditions on another entity name values of that entity's facts; a guard's
    condition is what the trigger must satisfy, so the guard applies to every value its trigger admits.
    """
    named: dict[tuple[str, str, Scalar], list[str]] = defaultdict(list)
    every: dict[str, list[str]] = defaultdict(list)

    def collect(rule: str, entity: str, conditions: Conditions) -> set[str]:
        listed = spec.entities[entity].allowed if entity in spec.entities else {}
        facts = set()
        for fact, value in conditions.items():
            if fact not in listed:
                continue
            facts.add(fact)
            values: set[Scalar]
            match value:
                case PerFact(cases=cases):
                    values = {item for items in cases.values() for item in items}
                case OneOf(values=listed_values):
                    values = set(listed_values)
                case NotEqual(value=excluded):
                    values = set[Scalar](listed[fact]) - {excluded}
                case _:
                    values = {value}
            for item in values:
                named[(entity, fact, item)].append(rule)
        return facts

    for invariant in spec.invariants:
        when, require = invariant.when, invariant.require
        if isinstance(when, EntityTrigger):
            names_none = not collect(invariant.id, when.entity, when.where)
            if names_none and spec.entities[when.entity].allowed:
                every[when.entity].append(invariant.id)
        if isinstance(require, EntityRequirement):
            collect(invariant.id, require.entity, require.where)
    for name, entity in spec.entities.items():
        if entity.allowed:
            every[name].insert(0, f"machine:{name}")
    return named, every


def listed_values(spec: Spec) -> str:
    """Each value a fact lists, its group and meaning, and which rules name it."""
    named, every = rule_values(spec)
    out = []
    for name, entity in sorted(spec.entities.items()):
        for fact, meanings in entity.meanings.items():
            group_of = {value: group for group, values in entity.groups.get(fact, {}).items() for value in values}
            rows = [
                [
                    esc(group_of.get(value, "")),
                    f"<code>{esc(value)}</code>",
                    esc(meaning),
                    " ".join(f"<code>{esc(rule)}</code>" for rule in named.get((name, fact, value), []))
                    or '<span class="muted">none</span>',
                ]
                for value, meaning in meanings.items()
            ]
            applies = " ".join(f"<code>{esc(rule)}</code>" for rule in every.get(name, []))
            out.append(
                f"<h4>{esc(name)}.{esc(fact)}</h4>"
                f'<p class="lede">Every {esc(name)}, whatever its {esc(fact)}: {applies}</p>'
                + table(["Group", "Value", "Meaning", "Rules naming it"], rows)
            )
    return "".join(out)


SETTLES: dict[bool | str, str] = {
    True: "must be terminal when its owner's journal closes",
    "final": "must be terminal when its owner's journal closes for good",
    False: "no close settles it",
}


def page_specification(spec: Spec) -> Page:
    machines = []
    for name, entity in sorted(spec.entities.items()):
        if not entity.constrained:
            continue
        edges = sum(len(targets) for targets in entity.edges.values())
        facts = (
            f"starts in {' | '.join(entity.initial)} · ends in {' | '.join(entity.terminal) or 'nothing'} · "
            f"{edges} edges · {SETTLES[entity.settles_before_close]}"
        )
        reasons = [(t.source, ", ".join(t.targets), t.why) for t in entity.transitions if t.why]
        why = (
            "<details><summary>Why these edges</summary><ul>"
            + "".join(f"<li><code>{esc(s)} → {esc(ts)}</code>: {esc(w)}</li>" for s, ts, w in reasons)
            + "</ul></details>"
            if reasons
            else ""
        )
        machines.append(
            f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
            f'<div class="muted">{esc(facts)}</div>'
            f'<div class="svgwrap">{machine_svg(spec, name)}</div>{why}</div>'
        )
    citations = []
    for boundary in spec.boundaries.values():
        for cite in boundary.cites:
            by, cited = cite.by, cite.cited
            citing = (
                f"{by.entity} reaching {by.reached}" if isinstance(by, EntitySide) else f"{boundary.name}.{by.message}"
            )
            named = (
                f"{cited.entity} reaching {cited.reached} (its {cited.fact})"
                if isinstance(cited, EntitySide)
                else f"the {boundary.name}.{cited.message} record"
            )
            citations.append([f"<code>{esc(boundary.name)}</code>", esc(f"{citing} names {named} in {by.fact}")])
    patterns: dict[str, list[Invariant]] = defaultdict(list)
    for invariant in spec.invariants:
        patterns[invariant.pattern].append(invariant)
    invariants = "".join(
        f"<h4>{esc(pattern)}</h4>"
        + table(
            ["Rule", "When", "Then", "Meaning"],
            [
                [
                    rule_link(i.id),
                    f"<code>{esc(trigger_text(spec, i))}</code>",
                    f"<code>{esc(requirement_text(spec, i))}</code>",
                    esc(i.summary),
                ]
                for i in rules
            ],
        )
        for pattern, rules in sorted(patterns.items())
    )
    body = (
        '<h3>System map</h3><div class="diagram svgwrap">' + system_svg(spec) + "</div><h3>State machines</h3>"
        '<p class="lede">Where an instance starts, which edges it may take, and when it must have settled. '
        "Every other edge is a violation; nothing may leave a terminal state.</p>"
        + f'<div class="machines">{"".join(machines)}</div>'
        + without_machine(spec)
        + "<h3>Citations</h3>"
        '<p class="lede">The only order the checker trusts across sources: a record that names another was written '
        "after it. Without the citation, a rule that needs the order is inconclusive.</p>"
        + table(["Boundary", "Citation"], citations)
        + "<h3>Invariants</h3>"
        '<p class="lede">Cross-entity rules, each in one fixed pattern. A condition never matches an absent fact. '
        'Each links to <a href="coverage.html#rules">where it was decided</a>.</p>'
        + invariants
        + "<h3>Listed values</h3>"
        '<p class="lede">The values a fact may take, as its declaration lists and groups them, and the rules '
        "whose trigger or requirement names each one. A value no rule names is still checked by the rules "
        "that apply to every value.</p>" + listed_values(spec)
    )
    lede = "What the checker holds the evidence to, from <code>assurance/spec/</code>: no test results here."
    edges = sum(len(targets) for entity in spec.entities.values() for targets in entity.edges.values())
    drawn = sum(entity.constrained for entity in spec.entities.values())
    teaser = f"{drawn} state machines, {edges} edges, {len(spec.invariants)} invariants"
    return Page("specification", "Specification", teaser, section("specification", "Specification", lede, body))
