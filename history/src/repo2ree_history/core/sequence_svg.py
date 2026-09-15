"""Render partial system executions as standalone SVG, like the repository's Python diagram emitters."""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from textwrap import wrap

from repo2ree_history.core.models import SystemExecution
from repo2ree_history.core.sequence import ordered_events, references
from repo2ree_history.core.validation import validate_execution

COLORS = {"api": "#2d6b8c", "client": "#7a3d6b", "core": "#3d7a56", "executor": "#a86a1b"}


def render_svg(execution: SystemExecution) -> str:
    issues = validate_execution(execution)
    invalid = [issue for issue in issues if issue.severity == "invalid"]
    if invalid:
        raise ValueError("invalid trace: " + "; ".join(issue.code for issue in invalid))
    events = ordered_events(execution)
    components = sorted({event.producer.component for event in events}) or ["recorder"]
    lane_width, margin, row_height, top = 390, 32, 150, 340
    width = margin * 2 + lane_width * len(components)
    height = top + row_height * len(events) + 60
    centers = {component: margin + lane_width * (i + 0.5) for i, component in enumerate(components)}
    positions = {
        event.event_id: (centers[event.producer.component], top + i * row_height) for i, event in enumerate(events)
    }
    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        '<title id="title">Master system trace — partial recorded execution</title>',
        '<desc id="description">All assigned observations in one possible causal display order. '
        "Component lanes group processes for readability, "
        "without establishing producer order. Hover over an observation "
        "for its full evidence and source locations.</desc>",
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        '<path d="M0,0 L8,4 L0,8" fill="none" stroke="#475569"/></marker></defs>',
        "<style>text{font-family:ui-monospace,monospace;fill:#172334;font-size:12px}.heading{font-family:system-ui,sans-serif;font-weight:600}.muted{fill:#536579}.edge{fill:none;stroke:#475569;stroke-width:1.5;marker-end:url(#arrow)}</style>",
        f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
    ]

    def text(x: float, y: float, value: object, css: str = "", size: int | None = None) -> None:
        style = f' style="font-size:{size}px"' if size else ""
        output.append(f'<text x="{x}" y="{y}" class="{css}"{style}>{escape(str(value))}</text>')

    text(margin, 42, "MASTER SYSTEM TRACE", "heading", 26)
    text(margin, 70, execution.execution_id, "muted", 14)
    counts = Counter(event.payload.kind for event in events)
    text(
        margin,
        98,
        f"{len(events)} observations · {counts['operation.completed']} command completions · "
        f"{counts['git_capture.observed']} Git captures · {counts['state.observed']} state observations",
    )
    text(margin, 124, "Partial recording · vertical position is display order, not elapsed time or proof of causality.")
    text(
        margin,
        146,
        "Arrows: explicit evidence links only. Correlations and exact source references: hover over each observation.",
    )
    text(
        margin,
        168,
        "Lanes group components; process instance and epoch remain in each observation. "
        "Unknown identities stay unknown.",
    )
    gap_counts = Counter(issue.code for issue in issues)
    gaps = "; ".join(f"{key}: {value}" for key, value in sorted(gap_counts.items()))
    for i, line in enumerate(wrap("INCOMPLETE — " + gaps, max(60, int((width - 64) / 7.3)))):
        text(margin, 194 + i * 18, line, "muted")
    output.append('<a href="evidence-report.md">')
    text(margin, 254, "Evidence report: unassigned observations, limitations, and artifact index", "muted")
    output.append("</a>")
    for component, x in centers.items():
        color = COLORS.get(component, "#475569")
        output.append(
            f'<path d="M{x} 312 V{height - 32}" stroke="{color}" stroke-opacity="0.25" stroke-dasharray="4 5"/>'
        )
        text(x - 168, 292, component.upper(), "heading", 18)
        instances = {event.producer.instance_id for event in events if event.producer.component == component}
        text(
            x - 168,
            314,
            f"{len(instances - {None})} known instances" + (" · unknown instance present" if None in instances else ""),
            "muted",
        )
    for event in events:
        x, y = positions[event.event_id]
        for reference in references(event):
            if reference not in positions:
                continue
            sx, sy = positions[reference]
            if sx == x:
                # Route along the card edge so intervening observations do not hide the link.
                bend = x + 182
                path = f"M{sx + 170} {sy + 60} H{bend} V{y + 60} H{x + 170}"
            else:
                path = f"M{sx} {sy + 124} V{y - 10} H{x} V{y}"
            output.append(
                f'<path class="edge" d="{path}"><title>'
                f"{escape(reference + ' supports ' + event.event_id)}</title></path>"
            )
        color = COLORS.get(event.producer.component, "#475569")
        tooltip = escape(json.dumps(event.model_dump(mode="json", exclude_none=True), indent=2))
        output.append(f'<g id="{escape(event.event_id, quote=True)}"><title>{tooltip}</title>')
        output.append(f'<rect x="{x - 170}" y="{y}" width="340" height="124" rx="6" fill="white" stroke="{color}"/>')
        output.append(f'<rect x="{x - 170}" y="{y + 8}" width="4" height="108" fill="{color}"/>')
        text(x - 157, y + 20, f"{event.event_id}  {event.payload.kind}", "heading")
        payload = event.payload.model_dump(exclude_none=True)
        label = payload.get("name") or (
            event.operation.operation
            if event.operation
            else payload.get("projection", {}).get("document", {}).get("label", event.payload.kind)
        )
        for i, line in enumerate(wrap(str(label), 43)[:2]):
            text(x - 157, y + 40 + i * 15, line)
        status = payload.get("outcome") or payload.get("capture_status") or payload.get("status") or ""
        text(x - 157, y + 76, status, "muted")
        if event.source_refs:
            ref = event.source_refs[0]
            locator = ref.locator.model_dump(exclude_none=True)
            location = (
                f"line {locator['line']}"
                if "line" in locator
                else str(locator.get("commit_id", locator.get("path", "record")))[:12]
            )
            text(x - 157, y + 96, f"Source: {ref.artifact_id} / {location}", "muted")
        text(
            x - 157,
            y + 114,
            f"{len(event.correlations)} correlations · "
            + (event.observed_at.isoformat() if event.observed_at else "time unknown"),
            "muted",
            10,
        )
        output.append("</g>")
    output.append("</svg>")
    return "\n".join(output) + "\n"
