"""Render one captured trace as a waterfall — the picture a span file cannot show you.

The trace files under ``test-artifacts/traces/`` answer "what happened" only in
the sense that grep does. This answers the question you actually have while
reading them: what called what, in which process, and where the time went.

Every number is read from the file. Nothing is inferred, and nothing is styled
into significance the capture does not support: a span with no recorded
duration draws as no bar rather than as a guess.

    python scripts/trace_journal.py TRACE.ndjson                      # list traces
    python scripts/trace_journal.py TRACE.ndjson --trace d6edcd       # -> SVG on stdout
    python scripts/trace_journal.py TRACE.ndjson --trace d6edcd -f html -o t.html
    python scripts/trace_journal.py TRACE.ndjson --trace d6edcd --shapes none
    python scripts/trace_journal.py TRACE.ndjson --trace d6edcd --all-spans

Two emitters over one model, as ``arch_graph.py`` emits one import graph as dot
or mermaid. ``svg`` is a file you can commit and embed; ``html`` hands the
measuring to a browser, which is better at it than the estimate below.

``--shapes inline`` (the default) prints each span's recorded arguments and
outputs beneath it. Legible for a single operation, and not legible somewhere
around a hundred spans; ``--shapes none`` leaves the bars and hover titles,
which is the form that scales.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

# ================================================
# Geometry
# ================================================
# Only the SVG emitter needs these: SVG has no layout engine, so positions are
# arithmetic and labels are measured against an assumed character width. The
# HTML emitter has a browser and needs none of it.

MARGIN = 16
NAME_MIN = 190
NAME_MAX = 520
TRACK_W = 400
AMT_W = 116
GUTTER = 16

HEADER_H = 30
ROW_H = 22
SHAPE_H = 13
GROUP_H = 26
INDENT = 12

NAME_SIZE = 11.0
SHAPE_SIZE = 9.5
# Advance width of one character in a monospace face, as a fraction of the font
# size. Now that the name column is sized from its own content, this only
# scales the canvas — being a few percent out is cosmetic rather than the thing
# that decides which labels get cut.
CHAR_W = 0.62

# Spans the ASGI instrumentation emits around every request. They carry no
# repo2ree facts and outnumber the domain spans several to one, so they are out
# by default and behind --all-spans when you are debugging the transport.
NOISE_SUFFIXES = (" http send", " http receive")

# Assigned to services in sorted order, so a given file always colours the same
# way. The first two are the pair this system actually has; the rest exist so a
# third service does not come out unstyled.
PALETTE = ("#2d6b8c", "#a86a1b", "#3d7a56", "#7a3d6b", "#8c552d")
PALETTE_DARK = ("#6ab3d8", "#e0a355", "#67b088", "#c98ab8", "#d8926a")

# Reserved for direction, and deliberately outside PALETTE: a note tinted like
# a service reads as another node rather than as an annotation about one. These
# two hues mean "given to" and "returned by" wherever they appear, whatever
# service the node belongs to.
IN_COLOUR = "#6b3fa0"
OUT_COLOUR = "#0f766e"


# ================================================
# Model
# ================================================


@dataclass
class Span:
    name: str
    span_id: str
    parent_id: str | None
    trace_id: str
    service: str
    start_ns: int
    end_ns: int
    attrs: dict[str, Any]
    status: str
    links: list[tuple[str, str]] = field(default_factory=list)
    depth: int = 0
    anchor: str = ""
    children: list[Span] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return (self.end_ns - self.start_ns) / 1e6

    def self_ms(self) -> float:
        """Time inside this span not covered by any child span.

        The generic form of "where did it actually go". A dispatch whose child
        command is far shorter than itself is spending the difference on
        something no span covers — process startup, transport, waiting — and
        that gap is the one thing a nested waterfall hides unless it is named.

        Children are merged as intervals rather than summed, because siblings
        here genuinely overlap: the agent request that carries a command and
        the command span relayed back out of the container describe the same
        stretch of time from two sides. Summing them double-counts it, which
        drives the parent's self time to a floor of zero and reports the
        overlap as though it were work.
        """
        covered = 0
        reach = self.start_ns
        for child in sorted(self.children, key=lambda c: c.start_ns):
            start = max(child.start_ns, reach)
            if child.end_ns > start:
                covered += child.end_ns - start
                reach = child.end_ns
        return max(0.0, self.duration_ms - covered / 1e6)


@dataclass
class Group:
    """One trace's spans, and why they are in this picture.

    A background run anchors its own trace and *links* back to the request that
    started it rather than descending from it, so the story of one operation
    spans more than one trace. Rendering them as separate groups keeps that
    visible: collapsing them into one tree would show a parent-child
    relationship the capture does not claim.
    """

    trace_id: str
    spans: list[Span]
    relation: str = ""


def _parse_iso_ns(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp() * 1e9)


def load_spans(path: Path) -> list[Span]:
    """Read the SDK-shaped span lines a trace file holds.

    Lines that are not spans, or are spans without both timestamps, are skipped
    rather than defaulted: a bar drawn from a missing time is a lie about the
    capture, and the capture is the only thing this tool is entitled to show.
    """
    spans: list[Span] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        context = raw.get("context")
        if not isinstance(context, dict) or not raw.get("start_time") or not raw.get("end_time"):
            continue
        status = raw.get("status") or {}
        links = [
            (_strip0x(link["context"].get("trace_id")), _strip0x(link["context"].get("span_id")))
            for link in raw.get("links") or []
            if isinstance(link.get("context"), dict)
        ]
        spans.append(
            Span(
                name=str(raw.get("name", "")),
                span_id=_strip0x(context.get("span_id")),
                parent_id=_strip0x(raw.get("parent_id")) or None,
                trace_id=_strip0x(context.get("trace_id")),
                service=str((raw.get("resource") or {}).get("attributes", {}).get("service.name", "unknown")),
                start_ns=_parse_iso_ns(str(raw["start_time"])),
                end_ns=_parse_iso_ns(str(raw["end_time"])),
                attrs=raw.get("attributes") or {},
                status=str(status.get("status_code", "UNSET")),
                links=links,
            )
        )
    return spans


def _strip0x(value: object) -> str:
    return str(value or "").removeprefix("0x")


def build_forest(spans: list[Span]) -> list[Span]:
    """Nest spans by parent and return the roots, each subtree in start order.

    A span whose parent is outside this set is treated as a root. That happens
    legitimately, which is why it is not reported as an error.
    """
    by_id = {span.span_id: span for span in spans}
    roots: list[Span] = []
    for span in spans:
        parent = by_id.get(span.parent_id or "")
        if parent is None:
            roots.append(span)
        else:
            parent.children.append(span)
    for span in spans:
        span.children.sort(key=lambda child: (child.start_ns, child.span_id))
    roots.sort(key=lambda span: (span.start_ns, span.span_id))
    return roots


def prune(spans: list[Span], patterns: list[str], keep: list[str]) -> list[Span]:
    """Narrow to *keep*, drop *patterns*, and re-parent whatever survives.

    Removing a node without re-parenting would sever the path through it and
    report a caller as unreachable, which is worse than showing the noise. So a
    dropped span's children adopt its nearest surviving ancestor, and the graph
    still says who ultimately reached what.
    """
    if not patterns and not keep:
        return spans

    def matches(name: str) -> bool:
        # A leading ``=`` means the whole name, not part of it. Substring is
        # the useful default for prefix families like ``docker.``, but it cannot
        # drop a name that is itself a prefix of another without taking that one
        # too — and those two are not always the same component's spans.
        return any(name == pattern[1:] if pattern.startswith("=") else pattern in name for pattern in patterns)

    by_id = {span.span_id: span for span in spans}
    # ``--only`` narrows to one altitude — the core-internal view of a trace,
    # say — and the re-parenting below is what makes that read as a graph
    # rather than a pile of roots: a kept span whose parents were all dropped
    # attaches to the nearest kept ancestor, or becomes a root if there is none.
    doomed = {
        span.span_id
        for span in spans
        if matches(span.name) or (keep and not any(pattern in span.name for pattern in keep))
    }

    def survivor(span: Span) -> str | None:
        parent_id = span.parent_id
        while parent_id in doomed:
            parent = by_id.get(parent_id or "")
            parent_id = parent.parent_id if parent else None
        return parent_id

    kept = [span for span in spans if span.span_id not in doomed]
    for span in kept:
        span.parent_id = survivor(span)
    return kept


def flatten(roots: list[Span]) -> list[Span]:
    """Depth-first pre-order, stamping depth and a re-run-stable anchor.

    The anchor never uses the span id, which is minted fresh on every
    execution. A document that cites ``agent.request(copy_open)`` still points
    at the same step after the next capture; one that cites a span id points at
    nothing.

    Same-named siblings are told apart by their ``repo2ree.operation`` where
    they carry one — three spans called ``agent.request`` are a copy_open, a
    copy_chunk and an exec_action, and saying so beats numbering them. An
    ordinal is the fallback, and a worse anchor: inserting a call renumbers
    every sibling after it, so references drift silently.
    """
    ordered: list[Span] = []

    def walk(span: Span, depth: int) -> None:
        span.depth = depth
        ordered.append(span)
        counts: defaultdict[str, int] = defaultdict(int)
        for child in span.children:
            counts[child.name] += 1
        operations = [str(child.attrs.get("repo2ree.operation", "")) for child in span.children]
        seen: defaultdict[str, int] = defaultdict(int)
        for child, operation in zip(span.children, operations, strict=True):
            seen[child.name] += 1
            if counts[child.name] == 1:
                child.anchor = child.name
            elif operation and operations.count(operation) == 1:
                child.anchor = f"{child.name}({operation})"
            else:
                child.anchor = f"{child.name}#{seen[child.name]}"
            walk(child, depth + 1)

    for root in roots:
        root.anchor = root.name
        walk(root, 0)
    return ordered


def collect_groups(by_trace: dict[str, list[Span]], trace_id: str) -> list[Group]:
    """The chosen trace, preceded by any trace it is linked from.

    Following the link is what makes the picture start where the work did. The
    HTTP request that begins an operation lives in its own trace and is joined
    to the background run by a link, so a renderer that only walks parents
    opens the story mid-air.
    """
    ordered = flatten(build_forest(by_trace[trace_id]))
    groups = [Group(trace_id, ordered, "")]
    seen = {trace_id}
    for span in ordered:
        for linked_trace, linked_span in span.links:
            if linked_trace in seen or linked_trace not in by_trace:
                continue
            seen.add(linked_trace)
            target = next((s for s in by_trace[linked_trace] if s.span_id == linked_span), None)
            relation = f"linked from {target.name}" if target else "linked from"
            groups.insert(0, Group(linked_trace, flatten(build_forest(by_trace[linked_trace])), relation))
    return groups


# ================================================
# Data shapes
# ================================================


def shape_lines(span: Span, max_chars: int) -> list[str]:
    """The span's recorded facts, packed into as few lines as fit.

    Grouped the way the tracing layer records them — ``arg`` for what went in,
    ``out`` for what came back — because that split is the thing worth seeing
    at a glance, and it is already how the keys are namespaced.
    """
    groups: list[tuple[str, list[str]]] = []
    for label, prefix in (("arg", "repo2ree.arg."), ("out", "repo2ree.output.")):
        pairs = [
            f"{key[len(prefix) :]}={_short(value)}"
            for key, value in sorted(span.attrs.items())
            if key.startswith(prefix)
        ]
        if pairs:
            groups.append((label, pairs))

    extra = [
        f"{key.rsplit('.', 1)[-1]}={_short(value)}"
        for key, value in sorted(span.attrs.items())
        if key in ("repo2ree.exec.argv", "repo2ree.exit_code", "repo2ree.run_id")
    ]
    if extra:
        groups.append(("···", extra))

    lines: list[str] = []
    for label, pairs in groups:
        current = label
        for pair in pairs:
            if len(current) + 2 + len(pair) > max_chars and current.strip() != label:
                lines.append(current)
                current = " " * len(label)
            current += f"  {pair}"
        lines.append(current)
    return lines


def _short(value: object, limit: int = 34) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _truncate(text: str, px: float) -> str:
    room = int(px / (NAME_SIZE * CHAR_W))
    return text if len(text) <= room else text[: max(1, room - 1)] + "…"


# ================================================
# Shared layout facts
# ================================================


@dataclass
class Scale:
    origin_ns: int
    span_ns: int
    services: list[str]

    def offset(self, span: Span) -> float:
        return (span.start_ns - self.origin_ns) / self.span_ns * 100

    def length(self, span: Span) -> float:
        return max((span.end_ns - span.start_ns) / self.span_ns * 100, 0.15)

    @property
    def total_ms(self) -> float:
        return self.span_ns / 1e6


def build_scale(groups: list[Group]) -> Scale:
    """One time axis across every group, so linked traces stay comparable.

    The request and the run it started overlap in wall-clock time; putting them
    on separate scales would draw them as though they did not.
    """
    spans = [span for group in groups for span in group.spans]
    origin = min(span.start_ns for span in spans)
    return Scale(
        origin_ns=origin,
        span_ns=max(max(span.end_ns for span in spans) - origin, 1),
        services=sorted({span.service for span in spans}),
    )


def _tooltip(span: Span, scale: Scale) -> str:
    return (
        f"{span.anchor}\n{span.service}\n"
        f"{span.duration_ms:.1f} ms total, {span.self_ms():.1f} ms self\n"
        f"starts +{(span.start_ns - scale.origin_ns) / 1e6:.1f} ms · status {span.status}"
    )


# ================================================
# SVG
# ================================================


def render_svg(groups: list[Group], scale: Scale, *, shapes: bool) -> str:
    name_w = min(
        NAME_MAX,
        max(
            NAME_MIN,
            max(span.depth * INDENT + len(span.anchor) * NAME_SIZE * CHAR_W for group in groups for span in group.spans)
            + 10,
        ),
    )
    track_x = MARGIN + name_w + GUTTER
    amt_x = track_x + TRACK_W + 14
    width = amt_x + AMT_W + MARGIN

    body: list[str] = []
    y = MARGIN + HEADER_H
    for group in groups:
        if group.relation:
            body.append(f'<text class="grp" x="{MARGIN}" y="{y + 10}">{escape(group.relation)} ↴</text>')
            y += GROUP_H
        for span in group.spans:
            indent = span.depth * INDENT
            fill = f"var(--c{scale.services.index(span.service)})"
            body.append(f"<g><title>{escape(_tooltip(span, scale))}</title>")
            if span.status == "ERROR":
                wide = width - 2 * MARGIN + 8
                body.append(f'<rect class="err" x="{MARGIN - 4}" y="{y - 3}" width="{wide}" height="{ROW_H}"/>')
            label = escape(_truncate(span.anchor, name_w - indent - 6))
            body.append(f'<text class="nm" x="{MARGIN + indent}" y="{y + 11}" fill="{fill}">{label}</text>')
            body.append(f'<rect class="trk" x="{track_x}" y="{y + 3}" width="{TRACK_W}" height="10"/>')
            bar_x = f"{track_x + scale.offset(span) / 100 * TRACK_W:.1f}"
            bar_w = f"{scale.length(span) / 100 * TRACK_W:.1f}"
            body.append(f'<rect x="{bar_x}" y="{y + 3}" width="{bar_w}" height="10" rx="2" fill="{fill}"/>')
            body.append(f'<text class="amt" x="{amt_x + AMT_W}" y="{y + 11}">{span.duration_ms:.1f} ms</text>')
            body.append("</g>")
            y += ROW_H

            if shapes:
                room = int((width - 2 * MARGIN - indent - 16) / (SHAPE_SIZE * CHAR_W))
                for line in shape_lines(span, room):
                    body.append(f'<text class="shp" x="{MARGIN + indent + 14}" y="{y + 9}">{escape(line)}</text>')
                    y += SHAPE_H
                y += 3

    height = y + MARGIN + 18
    header = (
        f'<text class="hd" x="{MARGIN}" y="{MARGIN + 12}">span</text>'
        f'<text class="hd" x="{track_x}" y="{MARGIN + 12}">0 ms</text>'
        f'<text class="hd amt" x="{track_x + TRACK_W}" y="{MARGIN + 12}">{scale.total_ms:.0f} ms</text>'
        f'<text class="hd amt" x="{amt_x + AMT_W}" y="{MARGIN + 12}">duration</text>'
        f'<line class="rule" x1="{MARGIN}" y1="{MARGIN + 19}" x2="{width - MARGIN}" y2="{MARGIN + 19}"/>'
    )
    legend = "".join(
        f'<rect x="{MARGIN + i * 190}" y="{height - 30}" width="9" height="9" rx="2" fill="var(--c{i})"/>'
        f'<text class="shp" x="{MARGIN + i * 190 + 14}" y="{height - 22}">{escape(service)}</text>'
        for i, service in enumerate(scale.services)
    )
    light = ";".join(f"--c{i}:{PALETTE[i % len(PALETTE)]}" for i in range(len(scale.services)))
    dark = ";".join(f"--c{i}:{PALETTE_DARK[i % len(PALETTE_DARK)]}" for i in range(len(scale.services)))
    face = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" font-family="{face}">
<style>
  svg {{ --bg:#fff; --ink:#131820; --muted:#5b6675; --track:#e8ecf1; --rule:#d8dde4; --err:#a8341b14; {light} }}
  @media (prefers-color-scheme: dark) {{
    svg {{ --bg:#0e1218; --ink:#e4e8ee; --muted:#93a0b1; --track:#222a34; --rule:#2a323d;
           --err:#e0645520; {dark} }}
  }}
  .bg {{ fill: var(--bg) }}
  .nm {{ font-size: {NAME_SIZE}px }}
  .shp {{ font-size: {SHAPE_SIZE}px; fill: var(--muted) }}
  .grp {{ font-size: 9.5px; fill: var(--muted); letter-spacing: .06em }}
  .amt {{ font-size: 10px; fill: var(--ink); text-anchor: end }}
  .hd {{ font-size: 9px; fill: var(--muted); letter-spacing: .08em }}
  .trk {{ fill: var(--track); rx: 2 }}
  .rule {{ stroke: var(--rule); stroke-width: 1 }}
  .err {{ fill: var(--err) }}
</style>
<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>
{header}
{"".join(body)}
{legend}
</svg>
"""


# ================================================
# HTML
# ================================================


def render_html(groups: list[Group], scale: Scale, *, shapes: bool, title: str) -> str:
    """The same model, measured by a browser instead of by the estimate above.

    Every place the SVG emitter counts characters, this hands the job to CSS —
    which is the honest division of labour, and the reason this emitter has no
    geometry section.
    """
    rows: list[str] = []
    for group in groups:
        if group.relation:
            rows.append(f'<div class="grp">{escape(group.relation)}</div>')
        for span in group.spans:
            colour = f"var(--c{scale.services.index(span.service)})"
            classes = "row" + (" err" if span.status == "ERROR" else "")
            rows.append(f'<div class="{classes}" title="{escape(_tooltip(span, scale))}">')
            rows.append(
                f'<div class="nm" style="padding-left:{span.depth * 14}px;color:{colour}">'
                f'<span class="dot" style="background:{colour}"></span>{escape(span.anchor)}</div>'
            )
            rows.append(
                f'<div class="trk"><i style="left:{scale.offset(span):.3f}%;'
                f'width:{scale.length(span):.3f}%;background:{colour}"></i></div>'
            )
            rows.append(f'<div class="amt">{span.duration_ms:.1f} ms</div>')
            rows.append(f'<div class="self">{span.self_ms():.1f} self</div>')
            rows.append("</div>")
            if shapes and (lines := shape_lines(span, 200)):
                body = "<br>".join(escape(line) for line in lines)
                rows.append(f'<div class="shp" style="padding-left:{span.depth * 14 + 16}px">{body}</div>')

    legend = "".join(
        f'<div><i style="background:var(--c{i})"></i>{escape(service)}</div>'
        for i, service in enumerate(scale.services)
    )
    light = ";".join(f"--c{i}:{PALETTE[i % len(PALETTE)]}" for i in range(len(scale.services)))
    dark = ";".join(f"--c{i}:{PALETTE_DARK[i % len(PALETTE_DARK)]}" for i in range(len(scale.services)))

    return f"""<title>{escape(title)}</title>
<style>
  :root {{ --bg:#f4f6f8; --card:#fff; --ink:#131820; --muted:#5b6675;
           --line:#d8dde4; --track:#e8ecf1; --errbg:#a8341b12; {light}; color-scheme:light }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0e1218; --card:#161c24; --ink:#e4e8ee; --muted:#93a0b1;
             --line:#2a323d; --track:#222a34; --errbg:#e064551c; {dark}; color-scheme:dark }}
  }}
  :root[data-theme="dark"] {{ --bg:#0e1218; --card:#161c24; --ink:#e4e8ee; --muted:#93a0b1;
           --line:#2a323d; --track:#222a34; --errbg:#e064551c; {dark}; color-scheme:dark }}
  :root[data-theme="light"] {{ --bg:#f4f6f8; --card:#fff; --ink:#131820; --muted:#5b6675;
           --line:#d8dde4; --track:#e8ecf1; --errbg:#a8341b12; {light}; color-scheme:light }}

  body {{ margin:0; padding:2.5rem 1.5rem 4rem; background:var(--bg); color:var(--ink);
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .wrap {{ max-width:1120px; margin:0 auto; display:flex; flex-direction:column; gap:1rem }}
  h1 {{ font-family: system-ui, sans-serif; font-size:1rem; font-weight:620; margin:0;
        letter-spacing:-.01em; text-wrap:balance }}
  .sub {{ font-family: system-ui, sans-serif; font-size:.8rem; color:var(--muted); margin:0 }}

  .sheet {{ background:var(--card); border:1px solid var(--line); border-radius:6px;
            overflow-x:auto; padding:.5rem 0 }}
  .head, .row {{ display:grid; grid-template-columns: minmax(11rem,22rem) minmax(14rem,1fr) 5.5rem 5rem;
                 gap:.9rem; align-items:center; padding:.18rem .9rem; min-width:640px }}
  .head {{ font-size:.62rem; letter-spacing:.09em; text-transform:uppercase;
           color:var(--muted); border-bottom:1px solid var(--line); padding-bottom:.4rem;
           margin-bottom:.3rem }}
  .row.err {{ background:var(--errbg) }}
  .nm {{ font-size:.76rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }}
  .dot {{ display:inline-block; width:6px; height:6px; border-radius:2px; margin-right:.45rem;
          vertical-align:middle }}
  .trk {{ position:relative; height:11px; background:var(--track); border-radius:2px }}
  .trk i {{ position:absolute; top:0; bottom:0; min-width:2px; border-radius:2px }}
  .amt, .self {{ font-size:.72rem; text-align:right; font-variant-numeric:tabular-nums }}
  .self {{ color:var(--muted) }}
  .shp {{ font-size:.68rem; color:var(--muted); line-height:1.75; padding-right:.9rem;
          padding-bottom:.3rem; white-space:pre-wrap; min-width:640px }}
  .grp {{ font-family:system-ui,sans-serif; font-size:.66rem; letter-spacing:.09em;
          text-transform:uppercase; color:var(--muted); padding:.7rem .9rem .25rem }}
  .legend {{ display:flex; gap:1.2rem; font-size:.7rem; color:var(--muted) }}
  .legend div {{ display:flex; align-items:center; gap:.4rem }}
  .legend i {{ width:9px; height:9px; border-radius:2px }}
</style>
<div class="wrap">
  <h1>{escape(title)}</h1>
  <p class="sub">{scale.total_ms:.1f} ms across {len(groups)} trace(s). Hover a row for self time and start offset.</p>
  <div class="sheet">
    <div class="head"><span>span</span><span>0 → {scale.total_ms:.0f} ms</span>
      <span style="text-align:right">duration</span><span style="text-align:right">self</span></div>
    {"".join(rows)}
  </div>
  <div class="legend">{legend}</div>
</div>
"""


# ================================================
# DOT
# ================================================
# The one shape graphviz is actually right for. A waterfall needs positions
# derived from time, which is why the SVG emitter computes its own; a call
# graph is a graph, so the layout is dot's job and not this file's.


NOTE_WIDTH = 44

# What a node was given, and what it gave back. Split rather than listed
# together because the direction is the question: a value appearing as an input
# here and an output there is the data moving, and one flat list of facts hides
# exactly that.
IN_GROUPS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("http", ("http.method", "http.route"), ""),
    # Two namespaces, one direction. ``cmd`` is the whole command envelope as a
    # dispatcher sent it; ``arg`` is the argument object the handler received.
    # A renderer that knew only one of them would show half the hops as having
    # no input at all.
    ("cmd", (), "repo2ree.cmd."),
    ("arg", (), "repo2ree.arg."),
    ("exec", ("repo2ree.exec.argv",), ""),
)
OUT_GROUPS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("http", ("http.status_code",), ""),
    ("out", (), "repo2ree.output."),
    ("exit", ("repo2ree.exit_code",), ""),
)


def zone_of(span: Span, rules: list[tuple[str, list[str]]]) -> str:
    """Which component emitted this span — read from the code, not guessed.

    Every tracer in this system is ``get_tracer(__name__)``, so the
    instrumentation scope names the module that opened the span, and its top
    package names the component. That is the authority: service name is too
    coarse (the supervisor shares a process with the API, core with the
    executor) and span *names* are not authority at all — ``agent.request`` is
    opened by the agent, not by the supervisor that will consume it, and only
    the scope says so.

    ``--zone`` remains as an override for spans whose scope is uninformative,
    such as third-party instrumentation.
    """
    for name, patterns in rules:
        if any(pattern in span.name for pattern in patterns):
            return name
    return span.service


def parse_zones(specs: list[str]) -> list[tuple[str, list[str]]]:
    rules: list[tuple[str, list[str]]] = []
    for spec in specs:
        name, _, patterns = spec.partition("=")
        if not patterns:
            raise SystemExit(f"--zone expects NAME=PATTERN[,PATTERN...], got {spec!r}")
        rules.append((name, [pattern for pattern in patterns.split(",") if pattern]))
    return rules


def node_key(span: Span) -> str:
    """Identity of a span across executions, not within one.

    The waterfall's anchor disambiguates siblings inside a single trace. A graph
    that merges traces needs a key meaning the same thing in all of them, so it
    leans on what the span records about itself rather than on where it sat.
    """
    operation = str(span.attrs.get("repo2ree.operation", ""))
    argv = str(span.attrs.get("repo2ree.exec.argv", ""))
    if argv:
        return f"{span.name}({argv.rsplit('/', 1)[-1]})"
    if operation and operation not in span.name:
        return f"{span.name}({operation})"
    return span.name


def note_lines(span: Span, groups: tuple[tuple[str, tuple[str, ...], str], ...], *, values: bool) -> list[str]:
    """The facts to hang beside a node, wrapped to a fixed column.

    Graphviz will not wrap a label, so a note that is not wrapped here is a note
    that sets the width of the whole graph. Values are folded onto continuation
    lines rather than truncated, because a digest cut in half identifies
    nothing — the point of showing it is that it can be matched to another.
    """
    rows: list[tuple[str, str]] = []
    for label, exact, prefix in groups:
        rows.extend(
            (label, f"{key.rsplit('.', 1)[-1]} = {span.attrs[key]}" if values else key)
            for key in exact
            if key in span.attrs
        )
        if prefix:
            rows.extend(
                (label, f"{key[len(prefix) :]} = {span.attrs[key]}" if values else key[len(prefix) :])
                for key in sorted(k for k in span.attrs if k.startswith(prefix))
            )

    lines: list[str] = []
    last = ""
    for label, text in rows:
        gutter = f"{label:<5}" if label != last else " " * 5
        last = label
        wrapped = textwrap.wrap(text, width=NOTE_WIDTH, subsequent_indent="  ") or [text]
        lines.append(gutter + wrapped[0])
        lines.extend(" " * 5 + more for more in wrapped[1:])
    return lines


def render_dot(
    spans: list[Span],
    *,
    notes: bool,
    merged: bool,
    zones: list[tuple[str, list[str]]],
) -> str:
    """The observed call graph, top to bottom, grouped by component.

    Durations are omitted on purpose: this answers what calls what and what
    moves through it, and a merged node has no single duration anyway —
    inventing a mean would put a number on the picture that no run produced.
    """
    by_id = {span.span_id: span for span in spans}
    services = sorted({span.service for span in spans})

    nodes: dict[str, Span] = {}
    occurrences: defaultdict[str, int] = defaultdict(int)
    edges: defaultdict[tuple[str, str], int] = defaultdict(int)
    for span in spans:
        key = node_key(span)
        nodes.setdefault(key, span)
        occurrences[key] += 1
        parent = by_id.get(span.parent_id or "")
        if parent is not None:
            edges[(node_key(parent), key)] += 1

    grouped: dict[str, list[str]] = {}
    for key, span in nodes.items():
        grouped.setdefault(zone_of(span, zones), []).append(key)

    lines = [
        "digraph trace {",
        "  rankdir=TB;",
        "  bgcolor=transparent;",
        "  compound=true;",
        "  nodesep=.35;",
        "  ranksep=.5;",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, penwidth=1.2];',
        '  edge [fontname="Helvetica", fontsize=9, color="#8a93a0", arrowsize=.7];',
        "",
    ]
    for index, (zone, keys) in enumerate(grouped.items()):
        # A node lives in exactly one cluster, and its notes belong to the same
        # component it annotates — so the rank rows are emitted inside the
        # cluster rather than beside it, which also keeps a note from being
        # pulled out of the box its node sits in.
        lines.append(f"  subgraph cluster_{index} {{")
        lines.append(f'    label="{_dot_escape(zone)}";')
        lines.append('    labeljust="l"; fontname="Helvetica"; fontsize=10; fontcolor="#6b7482";')
        lines.append('    style="rounded,dashed"; color="#b9c0c9"; margin=14;')
        for key in keys:
            lines.extend(_node_lines(key, nodes[key], services, occurrences, notes=notes, merged=merged))
        lines.append("  }")

    lines.append("")
    # A link is not a call, so it is not drawn like one. Without it the picture
    # of one operation opens twice: the request in one component, the run it
    # started in another, with nothing between them.
    for span in spans:
        for _, linked_span in span.links:
            source = by_id.get(linked_span)
            if source is not None:
                lines.append(
                    f'  "{node_key(source)}" -> "{node_key(span)}" '
                    f'[style=dashed, label="links", fontcolor="#8a93a0", color="#8a93a0"];'
                )

    # Every call edge is drawn the same. Marking process boundaries was tried
    # and removed: the only candidate signal is ``service.name``, which is a
    # resource attribute stamped once per process by whichever bootstrap won the
    # global provider — so a co-located component reports under its host's name
    # for some spans and its own for others. An edge "crossing" that is an
    # artifact of start-up order, not a fact about deployment.
    for (tail, head), count in sorted(edges.items()):
        label = f' [label="\u00d7{count}"]' if merged and count > 1 else ""
        lines.append(f'  "{tail}" -> "{head}"{label};')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _node_lines(
    key: str,
    span: Span,
    services: list[str],
    occurrences: defaultdict[str, int],
    *,
    notes: bool,
    merged: bool,
) -> list[str]:
    colour = PALETTE[services.index(span.service) % len(PALETTE)]
    seen = f"  \u00d7{occurrences[key]}" if merged and occurrences[key] > 1 else ""
    lines = [
        f'    "{key}" [label="{_dot_escape(key)}{seen}", color="{colour}", '
        f'fillcolor="{colour}18", fontcolor="{colour}"];'
    ]
    if not notes:
        return lines

    inbound = note_lines(span, IN_GROUPS, values=not merged)
    outbound = note_lines(span, OUT_GROUPS, values=not merged)
    for side, body, tint in (("in", inbound, IN_COLOUR), ("out", outbound, OUT_COLOUR)):
        if not body:
            continue
        label = "".join(f"{_dot_escape(line)}\\l" for line in body)
        lines.append(
            f'    "{key}::{side}" [shape=note, style=filled, fillcolor="{tint}0d", color="{tint}", '
            f'penwidth=1.4, fontname="Courier", fontsize=9, fontcolor="#3f4753", label="{label}"];'
        )
    # Ranked beside the node, and the connectors live *inside* the rank
    # subgraph rather than outside it with constraint=false. Outside, dot drops
    # them from ordering as well as from ranking and places the notes in
    # whatever order it likes — which put the output on the left. Inside, the
    # same edges both draw the connector and fix left-to-right order.
    row = ([f'"{key}::in"'] if inbound else []) + [f'"{key}"'] + ([f'"{key}::out"'] if outbound else [])
    lines.append(f"    {{ rank=same; {'; '.join(row)};")
    if inbound:
        lines.append(f'      "{key}::in" -> "{key}" [style=dotted, color="{IN_COLOUR}", arrowsize=.6];')
    if outbound:
        lines.append(f'      "{key}" -> "{key}::out" [style=dotted, color="{OUT_COLOUR}", arrowsize=.6];')
    lines.append("    }")
    return lines


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


# ================================================
# Graph page
# ================================================


def render_graph_page(dot_source: str, *, title: str) -> str:
    """Run graphviz over *dot_source* and inline the result in a standalone page.

    A bare ``.svg`` from dot is a fine file and a poor document: it carries no
    heading, no legend, and no theme, so whoever opens it has to already know
    what they are looking at. Inlining keeps the page self-contained — no
    sidecar to lose — and lets the surrounding chrome say what the colours mean.
    """
    rendered = subprocess.run(
        ["dot", "-Tsvg"],
        input=dot_source.encode(),
        capture_output=True,
        check=True,
    ).stdout.decode()
    # dot sizes the root <svg> in points; dropping that lets CSS scale it to the
    # page instead of overflowing on a narrow screen.
    body = re.sub(r'<svg width="[^"]+" height="[^"]+"', "<svg", rendered, count=1)
    return f"""<title>{escape(title)}</title>
<style>
  :root {{ --bg:#f4f6f8; --ink:#131820; --card:#fff; color-scheme:light }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1218; --ink:#e4e8ee; color-scheme:dark }} }}
  :root[data-theme="dark"] {{ --bg:#0e1218; --ink:#e4e8ee; color-scheme:dark }}
  :root[data-theme="light"] {{ --bg:#f4f6f8; --ink:#131820; color-scheme:light }}
  body {{ margin:0; padding:2.5rem 1.5rem 4rem; background:var(--bg); color:var(--ink);
          font-family: system-ui, -apple-system, "Segoe UI", sans-serif }}
  .wrap {{ max-width:1300px; margin:0 auto; display:flex; flex-direction:column; gap:1rem }}
  h1 {{ font-size:1rem; font-weight:620; margin:0; letter-spacing:-.01em;
        font-family: ui-monospace, Menlo, Consolas, monospace }}
  .key {{ display:flex; gap:1.4rem; font-size:.78rem; opacity:.85; flex-wrap:wrap }}
  .key span {{ display:flex; align-items:center; gap:.45rem }}
  .key i {{ width:11px; height:11px; border-radius:2px; display:inline-block }}
  /* Graphviz bakes a light palette into the SVG, so the sheet stays light in
     both themes rather than rendering dark strokes on a dark ground. */
  .sheet {{ background:var(--card); border-radius:6px; padding:1.2rem; overflow-x:auto;
            box-shadow:0 1px 3px #0002 }}
  @media (prefers-color-scheme: dark) {{ .sheet {{ background:#f7f8fa }} }}
  :root[data-theme="dark"] .sheet {{ background:#f7f8fa }}
  .sheet svg {{ max-width:100%; height:auto; display:block; margin:0 auto }}
</style>
<div class="wrap">
  <h1>{escape(title)}</h1>
  <div class="key">
    <span><i style="background:{IN_COLOUR}"></i>input — what the node was given</span>
    <span><i style="background:{OUT_COLOUR}"></i>output — what it returned</span>
    <span>dashed edge = span link · dashed box = component</span>
  </div>
  <div class="sheet">{body}</div>
</div>
"""


# ================================================
# CLI
# ================================================


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("trace_file", type=Path, help="an NDJSON trace file (session or by-test slice)")
    parser.add_argument("--trace", help="trace id, or any unique prefix; omit to list what the file holds")
    parser.add_argument("-f", "--format", choices=("svg", "html", "dot", "graph"), default="svg")
    parser.add_argument("-o", "--out", type=Path, help="write here instead of stdout")
    parser.add_argument("--shapes", choices=("inline", "none"), default="inline")
    parser.add_argument("--title", help="heading for the graph page; defaults to the root span's name")
    parser.add_argument("--all-spans", action="store_true", help="keep the ASGI http send/receive spans")
    parser.add_argument("--no-links", action="store_true", help="show only the named trace, not what links to it")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="TEXT",
        help="drop spans whose name contains TEXT (or equals it, as =TEXT), re-parenting their children",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="TEXT",
        help="keep only spans whose name contains TEXT, re-parenting across the rest (repeatable)",
    )
    parser.add_argument(
        "--zone",
        action="append",
        default=[],
        metavar="NAME=PATTERN[,PATTERN]",
        help="dot only: box spans whose name matches any PATTERN as component NAME (repeatable)",
    )
    args = parser.parse_args()

    spans = load_spans(args.trace_file)
    if not spans:
        print(f"no spans with timestamps in {args.trace_file}", file=sys.stderr)
        return 1
    if not args.all_spans:
        spans = [span for span in spans if not span.name.endswith(NOISE_SUFFIXES)]
    # Kept for the diagnostic below: after filtering, a trace that held only
    # spans the filters removed is indistinguishable from one that never
    # existed — and telling a caller to "be more specific" about an id that
    # was right sends them looking in the wrong place.
    traces_before_filtering = {span.trace_id for span in spans}
    spans = prune(spans, args.exclude, args.only)

    by_trace: defaultdict[str, list[Span]] = defaultdict(list)
    for span in spans:
        by_trace[span.trace_id].append(span)

    args.trace_given = bool(args.trace)
    if not args.trace and args.format != "dot":
        for trace_id, members in sorted(by_trace.items(), key=lambda item: -len(item[1])):
            root = min(members, key=lambda span: span.start_ns)
            print(f"{trace_id}  {len(members):3d} spans  {root.name}")
        return 0

    matches = [trace_id for trace_id in by_trace if trace_id.startswith(args.trace or "")]
    if args.trace_given and len(matches) != 1:
        filtered_out = [t for t in traces_before_filtering if t.startswith(args.trace or "")]
        if not matches and filtered_out:
            print(f"--trace {args.trace!r} has no spans left after --only/--exclude", file=sys.stderr)
        else:
            print(f"--trace {args.trace!r} matched {len(matches)} traces; be more specific", file=sys.stderr)
        return 1

    if args.format in ("dot", "graph"):
        # A named trace draws that one operation, link included, with its real
        # values — the question is what flowed. With no trace named it merges
        # the file, where the question is which paths exist at all and values
        # differ per run, so notes fall back to keys.
        if args.trace_given:
            subject = [span for group in collect_groups(dict(by_trace), matches[0]) for span in group.spans]
        else:
            subject = spans
        dot = render_dot(
            subject,
            notes=args.shapes == "inline",
            merged=not args.trace_given,
            zones=parse_zones(args.zone),
        )
        summary = f"{len({node_key(span) for span in subject})} nodes"
        if args.format == "dot":
            return _emit(dot, args.out, summary)
        title = args.title or (subject[0].name if subject else "trace")
        return _emit(render_graph_page(dot, title=title), args.out, summary)

    groups = (
        [Group(matches[0], flatten(build_forest(by_trace[matches[0]])), "")]
        if args.no_links
        else collect_groups(dict(by_trace), matches[0])
    )
    scale = build_scale(groups)
    inline = args.shapes == "inline"
    if args.format == "svg":
        out = render_svg(groups, scale, shapes=inline)
    else:
        title = f"{groups[-1].spans[0].anchor} — {args.trace_file.name}"
        out = render_html(groups, scale, shapes=inline, title=title)

    total = sum(len(group.spans) for group in groups)
    return _emit(out, args.out, f"{total} spans, {len(groups)} trace(s)")


def _emit(text: str, out: Path | None, summary: str) -> int:
    if out is None:
        print(text)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{out}  ({summary})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
