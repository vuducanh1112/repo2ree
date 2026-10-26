"""How the last receipt's tests exercised the specification, and where each rule was decided."""

from __future__ import annotations

from repo2ree_repoview.overview.drawing import machine_svg
from repo2ree_repoview.overview.exports import Operations, Spec
from repo2ree_repoview.overview.html import Page, esc, rule_anchor, section, table
from repo2ree_repoview.overview.pages.aggregate import without_machine
from repo2ree_repoview.overview.pages.operations import anchor, title
from repo2ree_repoview.overview.receipt import Decision, Exercised, Receipt, reached

TONE = {"passed": "ok", "violated": "no", "inconclusive": "ex"}
FINDINGS_SHOWN = 3


def decision_item(rule: str, decision: Decision) -> str:
    links = [f'<a href="{esc(decision.report)}">verdicts</a>'] if decision.report else []
    links += [
        f'<a href="{esc(trace)}#rule={esc(rule)}">trace {esc(trace.rsplit("/", 1)[-1][:8])}</a>'
        for trace in decision.traces
    ]
    excused = f' <span class="muted">excused: {esc(decision.excused)}</span>' if decision.excused else ""
    shown = [f for f in decision.findings if f.verdict != "passed"][:FINDINGS_SHOWN]
    findings = "<ul>" + "".join(f"<li>{esc(f.subject)}: {esc(f.reason)}</li>" for f in shown) + "</ul>" if shown else ""
    return (
        f'<li><span class="{TONE.get(decision.verdict, "ex")}">{esc(decision.verdict)}</span> '
        f"<code>{esc(decision.test)}</code> &times;{decision.triggered} · {' · '.join(links) or 'no report bundled'}"
        f"{excused}{findings}</li>"
    )


def decided_in(rule: str, decided: list[Decision]) -> str:
    """Tests that did not pass the rule in full view; those that did, folded."""
    if not decided:
        return '<span class="muted">no test</span>'
    failing = [d for d in decided if d.verdict != "passed"]
    passing = [d for d in decided if d.verdict == "passed"]
    shown = f'<ul class="decided">{"".join(decision_item(rule, d) for d in failing)}</ul>' if failing else ""
    folded = (
        f'<details><summary><span class="ok">{len(passing)} passed</span></summary>'
        f'<ul class="decided">{"".join(decision_item(rule, d) for d in passing)}</ul></details>'
        if passing
        else ""
    )
    return shown + folded


# Rules not tied to drawn operations, and what they judge.
WHOLE = {
    "machine": "every transition of its subject; traces show only violations",
    "boundary": "every exchange; traces show only violations",
    "evidence": "the dossier's sources",
    "reconciliation": "the persisted stores against the journal",
}


def shown_in(rule: str, kind: str, catalogue: Operations) -> str:
    if kind in WHOLE:
        return f'<span class="muted">{esc(WHOLE[kind])}</span>'
    found = [
        (op, tally.passed + tally.violated + tally.inconclusive)
        for op in catalogue.operations
        for tally in op.rules
        if tally.rule == rule
    ]
    links = [f'<a href="operations.html#{esc(anchor(op))}">{title(op)}</a> &times;{n}' for op, n in found]
    if len(links) <= 3:
        return " · ".join(links) or '<span class="muted">none drawn</span>'
    return f"<details><summary>{len(links)} operations</summary>{'<br>'.join(links)}</details>"


def page_coverage(
    spec: Spec,
    receipt: Receipt | None,
    exercised: Exercised,
    unreached: dict[str, str],
    decisions: dict[str, list[Decision]],
    catalogue: Operations,
) -> Page:
    edges, rules, extras = exercised.edges, exercised.rules, exercised.extras
    legend = (
        '<p class="legend"><span class="ok">— reached (count)</span><span class="ex">- - excused</span>'
        '<span class="no">- - unreached, not excused</span></p>'
    )
    machines = "".join(
        f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
        f'<div class="svgwrap">{machine_svg(spec, name, edges, unreached)}</div></div>'
        for name, entity in sorted(spec.entities.items())
        if entity.constrained
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
    patterns = {invariant.id: invariant.pattern for invariant in spec.invariants}
    kinds = {rule: decided[0].kind for rule, decided in decisions.items()}
    every_rule = list(dict.fromkeys([*decisions, *patterns]))
    rule_rows = []
    for rule in every_rule:
        count = rules.get(rule, 0)
        status = (
            f'<span class="ok">{count}</span>'
            if count
            else ('<span class="ex">excused</span>' if f"rule:{rule}" in unreached else '<span class="no">0</span>')
        )
        rule_rows.append(
            [
                f'<code id="{esc(rule_anchor(rule))}">{esc(rule)}</code>',
                esc(patterns.get(rule) or kinds.get(rule, "")),
                status,
                decided_in(rule, decisions.get(rule, [])),
                shown_in(rule, kinds.get(rule, ""), catalogue),
            ]
        )
    extra_rows = [
        [f"<code>{esc(subject)}</code>", f"<code>{esc(fact)}</code>" if fact else "the whole subject", str(count)]
        for (subject, fact), count in sorted(extras.items())
    ]
    body = (
        "<h3>State machines, with how often each edge was taken</h3>"
        + legend
        + f'<div class="machines">{machines}</div>'
        + without_machine(spec)
        + "<h3>Boundaries, with how often each message was recorded</h3>"
        + table(["Boundary", "Messages"], boundary_rows)
        + "<h3>Rules, and where each was decided</h3>"
        + '<p class="lede">Each rule with the tests that decided it, linked to their verdicts and traces, and '
        'the <a href="operations.html">operations</a> that triggered it.</p>'
        + table(["Rule", "Kind", "Triggered", "Decided in", "Triggered by"], rule_rows, "rules")
        + "<h3>Recorded beyond the vocabulary</h3>"
        + (
            table(["Subject", "Fact", "Records"], extra_rows)
            if extra_rows
            else '<p class="muted">Nothing: every record the tests left is declared in the vocabulary.</p>'
        )
    )
    lede = (
        "How the tests behind the last assurance-gate receipt exercised the specification, summed over their dossiers. "
        'Excused items are listed with their reasons on the <a href="assurance-gate.html">Assurance gate</a> page.'
    )
    teaser = f"How the last receipt's tests exercised the specification: {reached(receipt)} items reached"
    return Page("coverage", "Coverage", teaser, section("coverage", "Coverage", lede, body))
