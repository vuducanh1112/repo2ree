"""An aggregate: its evidence graph, and every part of its committed document with the operations that moved it."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from repo2ree_repoview.diagrams.ree import CAPTURES, COLOURS, DIGEST, PAIR, TREE, Role
from repo2ree_repoview.overview import figures
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.drawing import never_taken
from repo2ree_repoview.overview.exports import Aggregate, Spec, SubMachine
from repo2ree_repoview.overview.figures import diagram_origin, inlined
from repo2ree_repoview.overview.html import Page, esc, section
from repo2ree_repoview.overview.receipt import AggregateMoves, Move
from repo2ree_repoview.overview.spec_diagrams import evidence_drawing, part_drawing
from repo2ree_repoview.stamp import read_svg_stamp

DISALLOWED_SHOWN = 20
# How a page names an aggregate whose name is an acronym.
TITLES = {"Ree": "REE"}
# The drawing of an aggregate's document as its contract states it, and the recipe that draws it.
ANATOMIES = {
    "Ree": ("ree/anatomy.svg", "generate-ree-anatomy", ("contracts/ree/ree.schema.json", "contracts/ree/layout.json"))
}


def slug(aggregate: Aggregate) -> str:
    return aggregate.name.lower()


def title(aggregate: Aggregate) -> str:
    return TITLES.get(aggregate.name, aggregate.name)


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
            f' (part by part: <a href="{slug(drawn[name])}.html">{esc(title(drawn[name]))}</a>)'
            if name in drawn
            else ""
        )
        for name in names
    ]
    return (
        f'<p class="muted">No machine, so any move between their states, judged by their rules: {", ".join(items)}.</p>'
    )


def card(bundle: Bundle, aggregate: Aggregate, machine: SubMachine, moves: Counter[Move], note: str = "") -> str:
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
        + f'<div class="svgwrap">{inlined(bundle, part_drawing(aggregate.name, machine.name))}</div>{listed}</div>'
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


def _symbol(shape: str) -> str:
    return f'<svg width="30" height="14" viewBox="0 0 30 14" aria-hidden="true">{shape}</svg>'


def _arrow(color: str, dashed: bool = False, width: float = 1.5) -> str:
    dash = ' stroke-dasharray="4 3"' if dashed else ""
    return _symbol(
        f'<line x1="1" y1="7" x2="24" y2="7" stroke="{color}" stroke-width="{width:g}"{dash}/>'
        f'<path d="M23 3 L29 7 L23 11 Z" fill="{color}"/>'
    )


# What the evidence graph's shapes mean, drawn in the graph's own colours (overview/drawing.py).
EVIDENCE_LEGEND = (
    '<p class="legend symbols">'
    "<span>"
    + _symbol('<rect x="1" y="1" width="28" height="12" rx="5" fill="#dbeafe" stroke="#3b82f6"/>')
    + "receipt: by the operation that produces it; (each) for one per experiment</span>"
    "<span>"
    + _symbol(
        '<path d="M1 1 H24 L29 6 V13 H1 Z" fill="#e2ece8" stroke="#0f766e"/>'
        '<path d="M24 1 V6 H29" fill="none" stroke="#0f766e"/>'
    )
    + "field of the REE's definition</span>"
    f"<span>{_arrow('#64748b')}made from: stale when that receipt is produced again</span>"
    f"<span>{_arrow('#0f766e')}rests on: stale when that field moves</span>"
    f"<span>{_arrow('#0f766e', dashed=True)}about: applicable only while that field is declared</span>"
    '<span><b class="stales">stales N</b> re-running it makes N receipts stale</span>'
    '<span><b class="undeclared">applies undeclared</b> applicable even with nothing declared</span>'
    "</p>"
)


def _box(role: Role | None) -> str:
    fill, frame = COLOURS[role] if role else TREE
    return _symbol(
        f'<rect x="1" y="1" width="28" height="12" fill="{fill}" stroke="{frame}"/>'
        f'<rect x="1" y="1" width="28" height="4" fill="{frame}"/>'
    )


# What the anatomy's shapes mean, drawn in its own colours (diagrams/ree.py).
ANATOMY_LEGEND = (
    '<p class="legend symbols">'
    f"<span>{_box('definition')}section of the definition: what the author declares</span>"
    f"<span>{_box('receipt')}receipt: what a run observed, by the operation that writes it</span>"
    f"<span>{_box('bundle')}bundle and seal</span>"
    f"<span>{_box(None)}file tree: each entry, and how a capture carries it: "
    + " ".join(f'<b style="color:{colour};font-weight:400">{capture}</b>' for capture, colour in CAPTURES.items())
    + "</span>"
    f"<span>{_arrow(DIGEST)}a digest of that file; a declaration and the receipts that ran it meet there</span>"
    f"<span>{_arrow(PAIR)}the receipt records the declared field</span>"
    f"<span>{_arrow(PAIR, width=3)}the receipt holds the whole declared section</span>"
    f"<span>{_arrow(PAIR, dashed=True)}the receipt field has the declared section's fields</span>"
    "</p>"
)


def anatomy(aggregate: Aggregate, bundle: Bundle) -> str:
    if aggregate.name not in ANATOMIES:
        return ""
    drawing, recipe, contracts = ANATOMIES[aggregate.name]
    path = figures.DIAGRAMS / drawing
    origin = diagram_origin(bundle, read_svg_stamp(path)) if path.is_file() else ""
    return (
        "<h3>Anatomy</h3>"
        f'<p class="muted">Every part of the document, and the files it is about, as {codes(contracts)} state them. '
        "A path field names where it is resolved; a digest field points at the file it is the digest of. "
        f"Drawn by <code>just {esc(recipe)}</code>. {origin}</p>"
        + ANATOMY_LEGEND
        + f'<div class="diagram full">{inlined(bundle, drawing, recipe)}</div>'
    )


def page_aggregate(aggregate: Aggregate, moves: AggregateMoves, bundle: Bundle) -> Page:
    """Every part in the checker's order, one row of cards per group."""
    groups: dict[str, list[str]] = {}
    for machine in aggregate.machines:
        note = receipt_note(aggregate, machine.name) if machine.kind == "receipt" else ""
        groups.setdefault(machine.group, []).append(card(bundle, aggregate, machine, moves.of(machine.name), note))
    graph = (
        "<h3>Evidence graph</h3>"
        '<p class="muted">The receipts as the specification states them, and what each depends on.</p>'
        + EVIDENCE_LEGEND
        + f'<div class="diagram full">{inlined(bundle, evidence_drawing(aggregate.name))}</div>'
    )
    body = (
        anatomy(aggregate, bundle)
        + graph
        + "<h3>Parts</h3>"
        + summary(aggregate, moves)
        + LEGEND
        + "".join(f'<h4>{esc(group)}</h4><div class="parts">{"".join(cards)}</div>' for group, cards in groups.items())
    )
    name = title(aggregate)
    drawings = "anatomy, evidence graph" if aggregate.name in ANATOMIES else "evidence graph"
    teaser = f"The {name}'s {drawings}, its {len(aggregate.machines)} parts, and the operations that moved each"
    return Page(slug(aggregate), name, teaser, section(slug(aggregate), name, "", body))
