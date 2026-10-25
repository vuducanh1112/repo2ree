"""How each operation travels across components, and how far its checked evidence reaches."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import Lane, Line, Operation, Operations, Reach
from repo2ree_repoview.overview.html import Page, esc, rule_link, section, table
from repo2ree_repoview.overview.receipt import Evidence, Receipt

REACH: tuple[tuple[Reach, str], ...] = (
    ("checked", "a journal or Git record placed on the component, in every run"),
    ("exchanged", "only checked messages the component sent or was sent"),
    ("span", "only OpenTelemetry spans: context the checker does not read"),
    ("none", "not reached, or not in every run"),
)
NO_SEQUENCE = "no sequence: only the journal records it"

# Sequence layout: time gutter, component column, provenance column, row height, header height.
GUTTER, LANE, RIGHT, ROW, TOP = 70, 132, 150, 24, 60


def seconds(value: float | None) -> str:
    if value is None:
        return "&ndash;"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    return f"{value:.1f} s" if value < 90 else f"{value // 60:.0f} min {value % 60:.0f} s"


def provenance(line: Line) -> str:
    return "no spans" if line.provenance == "gap" else line.provenance


def anchor(operation: Operation) -> str:
    return f"op-{operation.name}-{operation.outcome or 'open'}"


def title(operation: Operation) -> str:
    tone = "ok" if operation.outcome in ("succeeded", "released") else "ex"
    return f'<code>{esc(operation.name)}</code> <span class="{tone}">{esc(operation.outcome or "open")}</span>'


def durations(operation: Operation) -> str:
    found = [i.duration for i in operation.instances if i.duration is not None]
    if not found:
        return "&ndash;"
    middle = seconds(statistics.median(found))
    return (
        middle
        if len(found) == 1
        else f'{middle} <span class="muted">({seconds(min(found))}&ndash;{seconds(max(found))})</span>'
    )


def rule_summary(operation: Operation) -> str:
    passed = sum(t.passed for t in operation.rules)
    violated = sum(t.violated for t in operation.rules)
    inconclusive = sum(t.inconclusive for t in operation.rules)
    parts = [f'<span class="ok">{passed} passed</span>'] if passed else []
    parts += [f'<span class="no">{violated} violated</span>'] if violated else []
    parts += [f'<span class="ex">{inconclusive} inconclusive</span>'] if inconclusive else []
    return " · ".join(parts) or '<span class="muted">none triggered</span>'


def mark(reach: Reach, lane: Lane | None = None) -> str:
    where = f"{esc(lane.label)}: " if lane else ""
    return f'<span class="reach reach-{reach}" title="{where}{reach}"></span>'


def reaches(operation: Operation, lanes: Sequence[Lane]) -> list[str]:
    if not operation.lines and not operation.elsewhere:
        return [f'<span class="muted" title="{NO_SEQUENCE}">&ndash;</span>' for _ in lanes]
    return [mark(operation.reach.get(lane.id, "none"), lane) for lane in lanes]


def matrix(catalogue: Operations) -> str:
    headers = ["Operation", "Runs", "Median (range)", *(lane.label for lane in catalogue.lanes), "Rules triggered"]
    rows = [
        [
            f'<a href="#{esc(anchor(op))}">{title(op)}</a>',
            str(len(op.instances)),
            durations(op),
            *reaches(op, catalogue.lanes),
            rule_summary(op),
        ]
        for op in catalogue.operations
    ]
    legend = "".join(f"<span>{mark(reach)} {esc(reach)}: {esc(meaning)}</span>" for reach, meaning in REACH)
    legend += f'<span><span class="muted">&ndash;</span> {NO_SEQUENCE}</span>'
    return f'<div class="table-scroll">{table(headers, rows, "operations")}</div><p class="legend">{legend}</p>'


def _frame(lanes: Sequence[Lane], x: dict[str, float], height: int) -> list[str]:
    """Process columns, and a lifeline per component."""
    parts: list[str] = []
    groups: list[list[int]] = []
    for index, lane in enumerate(lanes):
        if groups and lanes[groups[-1][0]].process == lane.process:
            groups[-1].append(index)
        else:
            groups.append([index])
    for group in groups:
        left, right = GUTTER + group[0] * LANE + 5, GUTTER + (group[-1] + 1) * LANE - 5
        parts.append(f'<rect x="{left}" y="6" width="{right - left}" height="{height - 12}" rx="8" fill="var(--bg)"/>')
        process = esc(lanes[group[0]].process)
        parts.append(f'<text class="proc" x="{(left + right) / 2}" y="22" text-anchor="middle">{process}</text>')
    for lane in lanes:
        parts.append(
            f'<line x1="{x[lane.id]}" y1="{TOP - 10}" x2="{x[lane.id]}" y2="{height - 8}" stroke="var(--line)" '
            'stroke-width="1.5"/>'
        )
        parts.append(
            f'<text class="lane-name" x="{x[lane.id]}" y="{TOP - 18}" text-anchor="middle">{esc(lane.label)}</text>'
        )
    return parts


def _message(line: Line, start: float, end: float, y: float) -> str:
    way = 1 if end > start else -1
    dash = "" if line.provenance in ("journal", "git") else ' stroke-dasharray="5 3"'
    weight = 2 if line.provenance == "journal" else 1.5
    tip = end - way * 7
    return (
        f'<line x1="{start + way * 6}" y1="{y}" x2="{tip}" y2="{y}" stroke="currentColor" '
        f'stroke-width="{weight}"{dash}/>'
        f'<path d="M{tip + way} {y - 4} L{end - way} {y} L{tip + way} {y + 4} Z" fill="currentColor"/>'
        f'<text x="{min(start, end) + 10}" y="{y - 5}">{esc(line.label)}</text>'
    )


def _note(line: Line, at: float, y: float, *, rightward: bool) -> str:
    if line.provenance == "gap":
        dot = (
            f'<line x1="{at}" y1="{y - 8}" x2="{at}" y2="{y + 8}" stroke="currentColor" stroke-width="3" '
            'stroke-dasharray="2 2"/>'
        )
    else:
        radius = 4.5 if line.provenance in ("journal", "git") else 3.5
        dot = f'<circle cx="{at}" cy="{y}" r="{radius}" fill="currentColor"/>'
    side, text_x = ("start", at + 10) if rightward else ("end", at - 10)
    return f'{dot}<text x="{text_x}" y="{y + 4}" text-anchor="{side}">{esc(line.label)}</text>'


def sequence_svg(lanes: Sequence[Lane], lines: Sequence[Line], runs: int, name: str) -> str:
    width = GUTTER + len(lanes) * LANE + RIGHT
    height = TOP + len(lines) * ROW + 16
    x = {lane.id: GUTTER + index * LANE + LANE / 2 for index, lane in enumerate(lanes)}
    # Notes on the last two components go to their left, inside the drawing.
    rightward = {lane.id: index < len(lanes) - 2 for index, lane in enumerate(lanes)}
    parts = _frame(lanes, x, height)
    for index, line in enumerate(lines):
        y = TOP + index * ROW + ROW / 2
        partial = line.seen < runs
        count = f'<tspan class="{"count-partial" if partial else "count"}"> · {line.seen}/{runs}</tspan>'
        row = [
            f'<text class="t" x="{GUTTER - 10}" y="{y + 4}" text-anchor="end">+{seconds(line.t)}</text>',
            f'<text class="prov" x="{width - RIGHT + 12}" y="{y + 4}">{esc(provenance(line))}{count}</text>',
        ]
        if line.to is not None and line.to in x and line.lane in x:
            row.append(_message(line, x[line.lane], x[line.to], y))
        elif line.to is None and line.lane in x:
            row.append(_note(line, x[line.lane], y, rightward=rightward[line.lane]))
        group_class = f"p-{esc(line.provenance)}" + (" partial" if partial else "")
        parts.append(f'<g class="{group_class}">{"".join(row)}</g>')
    label = f"How {esc(name)} travels across components"
    return f'<svg class="seq" viewBox="0 0 {width} {height}" role="img" aria-label="{label}">{"".join(parts)}</svg>'


def trace_link(bundle: Bundle, evidence: Evidence, source: str, ree: str) -> str:
    directory = evidence.verifications.get(source)
    if directory is not None and (bundle.root / directory / "traces" / f"{ree}.html").is_file():
        return f'<a href="{esc(directory)}/traces/{esc(ree)}.html"><code>{esc(ree[:8])}</code></a>'
    return f"<code>{esc(ree[:8])}</code>"


def detail(operation: Operation, lanes: Sequence[Lane], bundle: Bundle, evidence: Evidence) -> str:
    runs = len(operation.instances)
    chosen = operation.instances[operation.representative]
    facts = (
        f'<p class="muted">{runs} run{"s" if runs != 1 else ""} · {durations(operation)} · drawn from '
        f"{esc(chosen.test or chosen.source)}, REE {trace_link(bundle, evidence, chosen.source, chosen.ree)}"
        f" (the run of median duration)</p>"
    )
    drawing = (
        f'<div class="seq-panel">{sequence_svg(lanes, operation.lines, runs, operation.name)}</div>'
        if operation.lines
        else f'<p class="muted">{NO_SEQUENCE.capitalize()}, without spans to place it.</p>'
    )
    elsewhere = ""
    if operation.elsewhere:
        rows = [
            [
                esc(line.lane) + (f" → {esc(line.to)}" if line.to else ""),
                esc(line.label),
                esc(provenance(line)),
                f"{line.seen}/{runs}",
            ]
            for line in operation.elsewhere
        ]
        elsewhere = (
            f"<details><summary>Lines other runs show and this one does not ({len(rows)})</summary>"
            + table(["Component", "Line", "From", "Runs"], rows)
            + "</details>"
        )
    instance_rows = [
        [
            esc(i.test or i.source),
            trace_link(bundle, evidence, i.source, i.ree),
            seconds(i.duration),
            f'<span class="{"ok" if i.verdict == "passed" else "ex"}">{esc(i.verdict)}</span>',
        ]
        for i in operation.instances
    ]
    instances = (
        f"<details><summary>Every run ({runs})</summary>"
        + table(["Test", "REE", "Duration", "Dossier verdict"], instance_rows)
        + "</details>"
    )
    rule_rows = [[rule_link(t.rule), str(t.passed), str(t.violated), str(t.inconclusive)] for t in operation.rules]
    rules = (
        f"<details><summary>Rules its events triggered: {rule_summary(operation)}</summary>"
        + table(["Rule", "Passed", "Violated", "Inconclusive"], rule_rows)
        + "</details>"
        if rule_rows
        else ""
    )
    heading = f'<div class="card op" id="{esc(anchor(operation))}"><h3>{title(operation)}</h3>'
    return f"{heading}{facts}{drawing}{elsewhere}{instances}{rules}</div>"


def page_operations(catalogue: Operations, receipt: Receipt | None, bundle: Bundle, evidence: Evidence) -> Page:
    names = len({op.name for op in catalogue.operations})
    teaser = f"{names} operations in {len(catalogue.operations)} outcomes, across components"
    if receipt is None or not catalogue.operations:
        why = (
            "No assurance-gate receipt in this clone yet: run <code>just assurance-gate</code>."
            if receipt is None
            else "The last receipt's runs left no verification to draw operations from."
        )
        return Page("operations", "Operations", teaser, section("operations", "Operations", why, ""))
    undrawn = (
        "<h3>Not drawn</h3>"
        + table(
            ["Test", "Dossier verdict", "Why"],
            [
                [esc(u.test or u.source), esc(u.verdict) if u.verdict else "&ndash;", esc(u.reason)]
                for u in catalogue.undrawn
            ],
        )
        if catalogue.undrawn
        else ""
    )
    body = (
        "<h3>Which components each operation's checked evidence reaches</h3>"
        + matrix(catalogue)
        + undrawn
        + "<h3>How each operation travels</h3>"
        + '<p class="legend"><span class="p-journal">— journal (checked)</span>'
        '<span class="p-git">● Git (witnessed)</span>'
        '<span class="p-inferred">● attempt state, placed inside its command span</span>'
        '<span class="muted">- - span (context)</span><span class="ex">n/m: shown by n of m runs</span></p>'
        + "".join(detail(op, catalogue.lanes, bundle, evidence) for op in catalogue.operations)
    )
    lede = (
        f"The operations of the tests behind the receipt for <code>{esc(receipt.revision[:10])}</code>, by outcome. "
        "Each sequence is one run, with how many runs show each line; solid lines are checked, dashed are spans."
    )
    return Page("operations", "Operations", teaser, section("operations", "Operations", lede, body))
