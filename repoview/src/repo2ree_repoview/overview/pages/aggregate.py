"""An aggregate as one machine of machines: every part of its committed document, and the operations that moved it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from repo2ree_repoview.overview.drawing import never_taken, submachine_svg
from repo2ree_repoview.overview.exports import Aggregate, Spec, SubMachine
from repo2ree_repoview.overview.html import Page, esc, section
from repo2ree_repoview.overview.receipt import AggregateMoves, Move

DISALLOWED_SHOWN = 20


def slug(aggregate: Aggregate) -> str:
    return f"{aggregate.name.lower()}-machine"


def codes(names: Iterable[str]) -> str:
    return ", ".join(f"<code>{esc(name)}</code>" for name in names)


def without_machine(spec: Spec) -> str:
    """The entities that have no machine to draw, and the page that draws their parts, where one does."""
    names = sorted(name for name, entity in spec.entities.items() if not entity.constrained)
    if not names:
        return ""
    drawn = {name: a for a in spec.aggregates.values() for name in (a.name, a.receipt_entity)}
    items = [
        codes([name])
        + (
            f' (part by part: <a href="{slug(drawn[name])}.html">{esc(drawn[name].name)} machine</a>)'
            if name in drawn
            else ""
        )
        for name in names
    ]
    return (
        f'<p class="muted">No machine, so any move between their states, judged by their rules: {", ".join(items)}.</p>'
    )


def card(machine: SubMachine, moves: Counter[Move], note: str = "") -> str:
    never = never_taken(machine, moves)
    listed = (
        f'<details class="never"><summary>{len(never)} allowed, never taken</summary>'
        f"{'<br>'.join(esc(item) for item in never)}</details>"
        if never
        else ""
    )
    return (
        f'<div class="card part"><b>{esc(machine.name.removeprefix("definition."))}</b>'
        + (f'<div class="muted">{esc(note)}</div>' if note else "")
        + f'<div class="svgwrap">{submachine_svg(machine, moves)}</div>{listed}</div>'
    )


def receipt_note(aggregate: Aggregate, name: str) -> str:
    receipt = aggregate.receipts[name]
    basis = [*receipt.rests_on, *(f"the {other} receipt" for other in receipt.made_from)]
    return f"by {receipt.produced_by}; stale when {', '.join(basis) or 'nothing'} moves"


def summary(aggregate: Aggregate, moves: AggregateMoves) -> str:
    """How much of what the machines allow the tests took, and every move no edge allows.

    Counted without bulk operations, which may take nearly any edge and are drawn only where taken.
    """
    if not moves.recorded:
        return (
            '<p class="state-stale">The receipt\'s reports predate aggregate reporting: run '
            "<code>just judge-e2e</code> or the assurance gate to count the moves.</p>"
        )
    allowed = {
        (m.name, e.source, e.target, op) for m in aggregate.machines for e in m.edges for op in e.by if op not in m.bulk
    }
    taken = {(move.machine, move.source, move.target, move.operation) for move in moves.counts} & allowed
    tone = "no" if moves.disallowed else "ok"
    disallowed = "".join(
        f"<li>{esc(finding.subject)}: {esc(finding.reason)}</li>" for finding in moves.disallowed[:DISALLOWED_SHOWN]
    )
    return (
        f"<p>{moves.instances} instances over the receipt's tests; "
        f'<span class="ok">{len(taken)}</span> of {len(allowed)} allowed moves (an edge by an operation) taken; '
        f'<span class="{tone}">{len(moves.disallowed)}</span> moves no edge allows.</p>'
        + (f"<ul>{disallowed}</ul>" if disallowed else "")
    )


LEGEND = (
    '<p class="legend"><span class="ok">— taken: operation and count</span>'
    '<span class="no">- - allowed, never taken</span>'
    '<span class="bad">— no edge allows it (✗)</span></p>'
)


def page_aggregate(aggregate: Aggregate, moves: AggregateMoves) -> Page:
    """Every part in the checker's order, one row of cards per group."""
    groups: dict[str, list[str]] = {}
    for machine in aggregate.machines:
        note = receipt_note(aggregate, machine.name) if machine.kind == "receipt" else ""
        groups.setdefault(machine.group, []).append(card(machine, moves.of(machine.name), note))
    body = (
        summary(aggregate, moves)
        + LEGEND
        + "".join(f'<h3>{esc(group)}</h3><div class="parts">{"".join(cards)}</div>' for group, cards in groups.items())
    )
    title = f"{aggregate.name} machine"
    teaser = f"{len(aggregate.machines)} parts of the {aggregate.name}, and the operations that moved each"
    return Page(slug(aggregate), title, teaser, section(slug(aggregate), title, "", body))
