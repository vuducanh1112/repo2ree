"""What the checker holds the evidence to: machines, citations, invariants, and listed values."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from repo2ree_repoview.overview.drawing import machine_svg, system_svg
from repo2ree_repoview.overview.exports import Invariant, Spec
from repo2ree_repoview.overview.html import esc, section, table


def literal(value: Any) -> str:
    """A condition's value as written in the specification: names bare, anything else (``""``, ``false``) as JSON."""
    return value if isinstance(value, str) and value else json.dumps(value)


type Groups = dict[str, dict[str, tuple[str, ...]]]


def whole_groups(values: list[Any], groups: dict[str, tuple[str, ...]]) -> list[str]:
    """The groups that together list exactly ``values``, in declaration order; none when no such groups exist."""
    named = [group for group, members in groups.items() if set(members) <= set(values)]
    covered = {value for group in named for value in groups[group]}
    return named if covered == set(values) else []


def condition(name: str, value: Any, groups: Groups) -> str:
    """A condition as the specification states it: a value list that is whole groups reads as those groups."""
    if isinstance(value, dict) and "not" in value:
        return f"{name} ≠ {literal(value['not'])}"
    if isinstance(value, dict) and "per" in value:
        # The alternatives depend on the trigger's fact: one list for each of its values.
        cases = "; ".join(f"{key}: {', '.join(map(literal, items))}" for key, items in value["in"].items())
        return f"{name} by the trigger's {value['per']} ({cases})"
    if isinstance(value, dict) and "in" in value:
        if named := whole_groups(value["in"], groups.get(name, {})):
            return f"{name} ∈ {' ∪ '.join(named)}"  # noqa: RUF001 — the union sign, as the page shows it
        return f"{name} ∈ {{{', '.join(map(literal, value['in']))}}}"
    return f"{name} = {literal(value)}"


def where(conditions: dict[str, Any], groups: Groups) -> str:
    if not conditions:
        return ""
    return " where " + ", ".join(condition(name, value, groups) for name, value in conditions.items())


def entity_groups(spec: Spec, entity: str) -> Groups:
    return spec.entities[entity].groups if entity in spec.entities else {}


def trigger_text(spec: Spec, invariant: Invariant) -> str:
    when = invariant.when
    if when.kind == "entity":
        source = f" from {' | '.join(when.source)}" if when.source else ""
        return f"{when.entity}{source} → {' | '.join(when.to)}{where(when.where, entity_groups(spec, when.entity))}"
    return f"{when.boundary}.{when.message}{where(when.where, {})}"


def requirement_text(spec: Spec, invariant: Invariant) -> str:
    require = invariant.require
    if require is None:
        return f"eventually {' | '.join(invariant.eventually)}"
    if require.kind == "guard":
        trigger = invariant.when.entity if invariant.when.kind == "entity" else ""
        return where(require.where, entity_groups(spec, trigger)).removeprefix(" where ")
    if require.kind == "exclusion":
        partition = spec.entities[require.entity].partition
        return f"no {require.entity} in {' | '.join(require.in_states)} with the same {partition}"
    key = "its own key" if require.key_from == "$key" else require.key_from
    before = ", before it" if require.order == "before" else ""
    if require.kind == "entity":
        reached = " | ".join(require.reached)
        conditions = where(require.where, entity_groups(spec, require.entity))
        return f"{require.entity} keyed by {key} reached {reached}{conditions}{before}"
    return f"{require.boundary}.{require.message} keyed by {key} was recorded{before}"


def rule_values(spec: Spec) -> tuple[dict[tuple[str, str, str], list[str]], dict[str, list[str]]]:
    """((entity, fact, value) -> the rules whose trigger names that value, entity -> the rules naming none of its).

    A requirement's conditions on another entity name values of that entity's facts; a guard's
    condition is what the trigger must satisfy, so the guard applies to every value its trigger admits.
    """
    named: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    every: dict[str, list[str]] = defaultdict(list)

    def collect(rule: str, entity: str, conditions: dict[str, Any]) -> set[str]:
        listed = spec.entities[entity].allowed if entity in spec.entities else {}
        facts = set()
        for fact, value in conditions.items():
            if fact not in listed:
                continue
            facts.add(fact)
            if isinstance(value, dict) and "per" in value:
                values = {item for items in value["in"].values() for item in items}
            elif isinstance(value, dict) and "in" in value:
                values = set(value["in"])
            elif isinstance(value, dict) and "not" in value:
                values = set(listed[fact]) - {value["not"]}
            else:
                values = {value}
            for item in values:
                named[(entity, fact, item)].append(rule)
        return facts

    for invariant in spec.invariants:
        when, require = invariant.when, invariant.require
        names_none = when.kind == "entity" and not collect(invariant.id, when.entity, when.where)
        if when.kind == "entity" and names_none and spec.entities[when.entity].allowed:
            every[when.entity].append(invariant.id)
        if require is not None and require.kind == "entity":
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


def page_specification(spec: Spec) -> str:
    machines = []
    for name, entity in sorted(spec.entities.items()):
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
            citing = f"{by.entity} reaching {by.reached}" if by.kind == "entity" else f"{boundary.name}.{by.message}"
            named = (
                f"{cited.entity} reaching {cited.reached} (its {cited.fact})"
                if cited.kind == "entity"
                else f"the {boundary.name}.{cited.message} record"
            )
            citations.append([f"<code>{esc(boundary.name)}</code>", esc(f"{citing} names {named} in {by.fact}")])
    patterns: dict[str, list[Any]] = defaultdict(list)
    for invariant in spec.invariants:
        patterns[invariant.pattern].append(invariant)
    invariants = "".join(
        f"<h4>{esc(pattern)}</h4>"
        + table(
            ["Rule", "When", "Then", "Meaning"],
            [
                [
                    f"<code>{esc(i.id)}</code>",
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
        + "<h3>Citations</h3>"
        '<p class="lede">The only order the checker trusts across sources: a record that names another was written '
        "after it. Without the citation, a rule that needs the order is inconclusive.</p>"
        + table(["Boundary", "Citation"], citations)
        + "<h3>Invariants</h3>"
        '<p class="lede">Cross-entity rules, each in one fixed pattern. A condition never matches an absent fact.</p>'
        + invariants
        + "<h3>Listed values</h3>"
        '<p class="lede">The values a fact may take, as its declaration lists and groups them, and the rules '
        "whose trigger or requirement names each one. A value no rule names is still checked by the rules "
        "that apply to every value.</p>" + listed_values(spec)
    )
    lede = "What the checker holds the evidence to, from <code>specifications/behaviour/</code>: no test results here."
    return section("specification", "Specification", lede, body)
