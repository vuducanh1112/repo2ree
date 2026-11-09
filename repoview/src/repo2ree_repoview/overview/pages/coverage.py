"""How the tests behind the last receipt, and the showcases' newest runs, exercised the specification.

Both pages say the same things of their own tests: each machine's edges and each boundary's messages
with how often they were recorded, and each rule with the tests that decided it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import Operations, Showcase, ShowcaseRuns, ShowcaseTest, Spec
from repo2ree_repoview.overview.figures import inlined
from repo2ree_repoview.overview.html import Page, esc, in_frame, rule_anchor, section, table
from repo2ree_repoview.overview.pages.aggregate import without_machine
from repo2ree_repoview.overview.pages.gates import evidence_links
from repo2ree_repoview.overview.pages.operations import anchor, title
from repo2ree_repoview.overview.receipt import (
    Decision,
    Evidence,
    Exercised,
    Receipt,
    RunRecord,
    TierNeed,
    reached,
)
from repo2ree_repoview.overview.spec_diagrams import coverage_drawing, showcase_coverage_drawing

TONE = {"passed": "ok", "violated": "no", "inconclusive": "ex"}
FINDINGS_SHOWN = 3


SHOWCASES = "showcase-gate"


def decision_item(rule: str, decision: Decision, origin: str = "coverage") -> str:
    links = [f'<a href="{esc(in_frame(decision.report, origin))}">verdicts</a>'] if decision.report else []
    links += [
        f'<a href="{esc(in_frame(trace, origin, f"rule={rule}"))}">trace {esc(trace.rsplit("/", 1)[-1][:8])}</a>'
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


def decided_in(rule: str, decided: list[Decision], origin: str = "coverage") -> str:
    """Tests that did not pass the rule in full view; those that did, folded."""
    if not decided:
        return '<span class="muted">no test</span>'
    failing = [d for d in decided if d.verdict != "passed"]
    passing = [d for d in decided if d.verdict == "passed"]
    shown = f'<ul class="decided">{"".join(decision_item(rule, d, origin) for d in failing)}</ul>' if failing else ""
    folded = (
        f'<details><summary><span class="ok">{len(passing)} passed</span></summary>'
        f'<ul class="decided">{"".join(decision_item(rule, d, origin) for d in passing)}</ul></details>'
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
    "aggregate": "every move of every part of the committed document",
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


def coverage_body(
    spec: Spec,
    exercised: Exercised,
    unreached: dict[str, str],
    decisions: dict[str, list[Decision]],
    catalogue: Operations | None,
    bundle: Bundle,
    drawing: Callable[[str], str],
    origin: str,
) -> str:
    """The machines, boundaries, rules, and stray records, as one page's tests exercised them.

    ``catalogue`` is the operations those tests were folded into; None leaves out where each rule was triggered.
    """
    edges, rules, extras = exercised.edges, exercised.rules, exercised.extras
    legend = (
        '<p class="legend"><span class="ok">— reached (count)</span><span class="ex">- - excused</span>'
        '<span class="no">- - unreached, not excused</span></p>'
    )
    machines = "".join(
        f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
        f'<div class="svgwrap">{inlined(bundle, drawing(name))}</div></div>'
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
        row = [
            f'<code id="{esc(rule_anchor(rule))}">{esc(rule)}</code>',
            esc(patterns.get(rule) or kinds.get(rule, "")),
            status,
            decided_in(rule, decisions.get(rule, []), origin),
        ]
        rule_rows.append([*row, shown_in(rule, kinds.get(rule, ""), catalogue)] if catalogue else row)
    extra_rows = [
        [f"<code>{esc(subject)}</code>", f"<code>{esc(fact)}</code>" if fact else "the whole subject", str(count)]
        for (subject, fact), count in sorted(extras.items())
    ]
    headers = ["Rule", "Kind", "Triggered", "Decided in", *(["Triggered by"] if catalogue else [])]
    rules_lede = "Each rule with the tests that decided it, linked to their verdicts and traces" + (
        ', and the <a href="operations.html">operations</a> that triggered it.' if catalogue else "."
    )
    return (
        "<h3>State machines, with how often each edge was taken</h3>"
        + legend
        + f'<div class="machines">{machines}</div>'
        + without_machine(spec)
        + "<h3>Boundaries, with how often each message was recorded</h3>"
        + table(["Boundary", "Messages"], boundary_rows)
        + "<h3>Rules, and where each was decided</h3>"
        + f'<p class="lede">{rules_lede}</p>'
        + table(headers, rule_rows, "rules")
        + "<h3>Recorded beyond the vocabulary</h3>"
        + (
            table(["Subject", "Fact", "Records"], extra_rows)
            if extra_rows
            else '<p class="muted">Nothing: every record the tests left is declared in the vocabulary.</p>'
        )
    )


def page_coverage(
    spec: Spec,
    receipt: Receipt | None,
    exercised: Exercised,
    unreached: dict[str, str],
    decisions: dict[str, list[Decision]],
    catalogue: Operations,
    bundle: Bundle,
) -> Page:
    body = coverage_body(spec, exercised, unreached, decisions, catalogue, bundle, coverage_drawing, "coverage")
    lede = (
        "How the tests behind the last assurance-gate receipt exercised the specification, summed over their dossiers. "
        'Excused items are listed with their reasons on the <a href="assurance-gate.html">Assurance gate</a> page. '
        f'The showcases have theirs on the <a href="{SHOWCASES}.html">Showcase gate</a> page.'
    )
    teaser = f"How the last receipt's tests exercised the specification: {reached(receipt)} items reached"
    return Page("coverage", "Coverage", teaser, section("coverage", "Coverage", lede, body))


def showcase_rows(
    showcases: ShowcaseRuns, records: dict[str, RunRecord], verdicts: dict[tuple[str, str], str] | None
) -> list[list[str]]:
    rows = []
    for tier in showcases.tiers:
        machine = esc(tier.environment) if tier.environment else '<span class="muted">default stack</span>'
        record = records.get(tier.run) if tier.run else None
        if tier.run is None or record is None:
            missing = f'<span class="no">no run in this clone</span>: <code>{esc(tier.recipe)}</code>'
            rows.append([f"<code>{esc(tier.tier)}</code>", esc(tier.surface), machine, missing, "", ""])
            continue
        name = Path(tier.run).name
        outcomes = Counter(test.outcome or "unknown" for test in record.tests)
        judged = Counter((verdicts or {}).get((name, test.name), "not assessed") for test in record.tests)
        ran = " · ".join(
            f'<span class="{"ok" if outcome == "passed" else "no"}">{count} {esc(outcome)}</span>'
            for outcome, count in outcomes.items()
        )
        behaved = " · ".join(
            f'<span class="{TONE.get(verdict, "ex")}">{count} {esc(verdict)}</span>'
            for verdict, count in judged.items()
        )
        tally = f"{ran}<br>behaviour: {behaved}"
        built = f"{esc(record.build_revision[:10])}{f', {esc(record.platform)}' if record.platform else ''}"
        rows.append(
            [f"<code>{esc(tier.tier)}</code>", esc(tier.surface), machine, f"<code>{esc(name)}</code>", built, tally]
        )
    return rows


def test_title(test: ShowcaseTest) -> str:
    """A test as its file and its own name, without repeating where it is."""
    if test.test is None:
        return f"<code>{esc(Path(test.file).name)}</code>"
    own = test.test.split("::", 1)[-1] if test.surface == "api" else test.test.split(" > ", 1)[-1]
    return f'<code>{esc(Path(test.file).name)}</code><br><span class="muted">{esc(own)}</span>'


def outcome_of(record: RunRecord | None, test: str) -> str:
    found = next((run_test.outcome for run_test in record.tests if run_test.name == test), "") if record else ""
    return f'<span class="{"ok" if found == "passed" else "no"}">{esc(found or "unknown")}</span>'


def showcase_section(
    showcase: Showcase,
    tiers: dict[str, str],
    records: dict[str, RunRecord],
    verdicts: dict[tuple[str, str], str] | None,
    evidence: Evidence,
    bundle: Bundle,
) -> str:
    rows = []
    for test in showcase.tests:
        if test.run is None or test.test is None:
            missing = f'<span class="no">not in this clone</span>: <code>{esc(tiers.get(test.tier, ""))}</code>'
            rows.append([esc(test.workflow or ""), esc(test.surface), test_title(test), missing, "", ""])
            continue
        key = (Path(test.run).name, test.test)
        verdict = (verdicts or {}).get(key, "not assessed")
        rows.append(
            [
                esc(test.workflow or ""),
                esc(test.surface),
                test_title(test),
                outcome_of(records.get(test.run), test.test),
                f'<span class="{TONE.get(verdict, "ex")}">{esc(verdict)}</span>',
                evidence_links(bundle, evidence.tests.get(key), SHOWCASES),
            ]
        )
    machine = f" · API on <code>{esc(showcase.environment)}</code>" if showcase.environment else ""
    kind = "" if showcase.kind == "showcase" else ' <span class="muted">feature</span>'
    return f'<h4 id="showcase-{esc(showcase.name)}"><code>{esc(showcase.name)}</code>{kind}{machine}</h4>' + table(
        ["Workflow", "Surface", "Test", "Outcome", "Behaviour", "Evidence"], rows
    )


def need_rows(needs: list[TierNeed]) -> list[list[str]]:
    rows = []
    for need in needs:
        if need.current is not None:
            proven = f'<span class="ok">current</span>: <code>{esc(Path(need.current.run).name)}</code> on '
            rows.append([f"<code>{esc(need.tier)}</code>", esc(need.place), proven + esc(need.current.machine)])
            continue
        last = f"; last proven on <code>{esc((need.last.revision or '?')[:10])}</code>" if need.last else ""
        needed = f'<span class="no">needed</span>: <code>just {esc(need.recipe)}</code>{last}'
        rows.append([f"<code>{esc(need.tier)}</code>", esc(need.place), needed])
    return rows


def page_showcase_coverage(
    spec: Spec,
    showcases: ShowcaseRuns,
    records: dict[str, RunRecord],
    verdicts: dict[tuple[str, str], str] | None,
    exercised: Exercised,
    decisions: dict[str, list[Decision]],
    evidence: Evidence,
    bundle: Bundle,
    needs: list[TierNeed],
) -> Page:
    tiers = {tier.tier: tier.recipe for tier in showcases.tiers}
    listed = "".join(showcase_section(s, tiers, records, verdicts, evidence, bundle) for s in showcases.showcases)
    runs = table(
        ["Tier", "Surface", "Machine", "Run", "Built from", "Outcomes; behaviour as this tree judges it"],
        showcase_rows(showcases, records, verdicts),
    )
    body = (
        "<h3>What the gate requires of HEAD</h3>"
        + (
            table(["Tier", "Where", "Receipt"], need_rows(needs))
            if needs
            else '<p class="muted">The policy names no showcase gate.</p>'
        )
        + "<h3>Each showcase, in its newest run</h3>"
        + listed
        + "<h3>The runs they come from</h3>"
        + runs
        + "<h2>Coverage</h2>"
        + '<p class="lede">How these tests exercised the specification, summed over their dossiers. Nothing they '
        'leave unreached is excused; the assurance gate\'s tests are on the <a href="coverage.html">Coverage</a> '
        "page.</p>" + coverage_body(spec, exercised, {}, decisions, None, bundle, showcase_coverage_drawing, SHOWCASES)
    )
    tests = sum(len(record.tests) for record in records.values())
    lede = (
        "Each showcase, authoring and review, through the API and the browser: the newest run of each showcase tier "
        "in this clone that ran every test, judged and drawn by this tree's checker and traceview. "
        "<code>just showcase-gate</code> proves the tiers it requires with a receipt each, on each platform."
    )
    teaser = f"Each showcase's tests and their coverage: {tests} tests in {len(records)} runs"
    return Page(SHOWCASES, "Showcase gate", teaser, section(SHOWCASES, "Showcase gate", lede, body))
