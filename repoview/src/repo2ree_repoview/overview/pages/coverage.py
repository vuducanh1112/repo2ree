"""How the last receipt's tests exercised the specification."""

from __future__ import annotations

from repo2ree_repoview.overview.drawing import machine_svg
from repo2ree_repoview.overview.exports import Spec
from repo2ree_repoview.overview.html import Page, esc, section, table
from repo2ree_repoview.overview.receipt import Exercised, Receipt, reached


def page_coverage(spec: Spec, receipt: Receipt | None, exercised: Exercised, unreached: dict[str, str]) -> Page:
    edges, rules, extras = exercised.edges, exercised.rules, exercised.extras
    legend = (
        '<p class="legend"><span class="ok">— reached (count)</span><span class="ex">- - excused</span>'
        '<span class="no">- - unreached, not excused</span></p>'
    )
    machines = "".join(
        f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
        f'<div class="svgwrap">{machine_svg(spec, name, edges, unreached)}</div></div>'
        for name, entity in sorted(spec.entities.items())
    )
    boundary_rows = [
        [
            f"<code>{esc(b.name)}</code>",
            " ".join(
                f'<span class="badge">{esc(m)} · {edges.get(f"{b.name}: {m}", 0)}</span>'
                for m in [*b.messages, "abandoned"]
            ),
        ]
        for b in spec.boundaries.values()
    ]
    invariant_rows = []
    for invariant in spec.invariants:
        count = rules.get(invariant.id, 0)
        status = (
            f'<span class="ok">{count}</span>'
            if count
            else (
                '<span class="ex">excused</span>'
                if f"rule:{invariant.id}" in unreached
                else '<span class="no">0</span>'
            )
        )
        invariant_rows.append([f"<code>{esc(invariant.id)}</code>", esc(invariant.pattern), status])
    extra_rows = [
        [f"<code>{esc(subject)}</code>", f"<code>{esc(fact)}</code>" if fact else "the whole subject", str(count)]
        for (subject, fact), count in sorted(extras.items())
    ]
    body = (
        "<h3>State machines, with how often each edge was taken</h3>"
        + legend
        + f'<div class="machines">{machines}</div>'
        + "<h3>Boundaries, with how often each message was recorded</h3>"
        + table(["Boundary", "Messages"], boundary_rows)
        + "<h3>Invariants, with how often each was triggered</h3>"
        + table(["Rule", "Pattern", "Triggered"], invariant_rows)
        + "<h3>Recorded beyond the vocabulary</h3>"
        + (
            table(["Subject", "Fact", "Records"], extra_rows)
            if extra_rows
            else '<p class="muted">Nothing: every record the tests left is declared in the vocabulary.</p>'
        )
    )
    lede = (
        "How the tests behind the last behaviour receipt exercised the specification, summed over their dossiers. "
        'Excused items are listed with their reasons on the <a href="behaviour-gate.html">Behaviour gate</a> page.'
    )
    teaser = f"How the last receipt's tests exercised the specification: {reached(receipt)} items reached"
    return Page("coverage", "Coverage", teaser, section("coverage", "Coverage", lede, body))
