"""Graphviz drawings of the specification: one machine, and the system map."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from repo2ree_repoview.graphviz import inline_svg
from repo2ree_repoview.graphviz import quote as q
from repo2ree_repoview.overview.exports import Spec
from repo2ree_repoview.overview.html import esc


def dot_svg(source: str) -> str:
    # Graphviz names the font it measured with; the page draws them all in its own sans-serif.
    return re.sub(r'font-family="[^"]*"', 'font-family="system-ui,sans-serif"', inline_svg(source))


def machine_svg(
    spec: Spec, name: str, edges: Counter[str] | None = None, unreached: dict[str, str] | None = None
) -> str:
    """One machine. With ``edges``, each edge carries how often the receipt's tests took it; without, the spec alone."""
    entity = spec.entities[name]
    why = {(t.source, target): t.why for t in entity.transitions for target in t.targets if t.why}
    lines = [
        "digraph machine {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2;',
        '  node [shape=box, style="rounded,filled", fillcolor="#eef2f7", color="#64748b", fontsize=10];',
        '  edge [fontsize=9, color="#64748b", fontcolor="#334155"];',
        '  "(none)" [shape=point, width=0.12, color="#334155"];',
    ]
    for state in entity.states:
        terminal = state in entity.terminal
        lines.append(f'  {q(state)} [peripheries={2 if terminal else 1}, tooltip="{esc(entity.states[state])}"];')
    pairs = [("(none)", state) for state in entity.initial] + [
        (source, target) for source, targets in entity.edges.items() for target in sorted(targets)
    ]
    for source, target in pairs:
        key = f"{name} {source} -> {target}"
        if edges is None:
            tip = f', tooltip="{esc(why[(source, target)])}"' if (source, target) in why else ""
            lines.append(f'  {q(source)} -> {q(target)} [color="#475569"{tip}];')
            continue
        count = edges.get(key, 0)
        if count:
            style = f'label="{count}", color="#0f766e", fontcolor="#0f766e", penwidth=1.6'
        elif unreached and key in unreached:
            style = (
                f'label="excused", style=dashed, color="#b45309", fontcolor="#b45309", tooltip="{esc(unreached[key])}"'
            )
        else:
            style = 'label="0", style=dashed, color="#dc2626", fontcolor="#dc2626"'
        lines.append(f"  {q(source)} -> {q(target)} [{style}];")
    lines.append("}")
    return dot_svg("\n".join(lines))


def system_svg(spec: Spec) -> str:
    lines = [
        "digraph system {",
        '  rankdir=LR; compound=true; bgcolor="transparent"; pad=0.2;',
        "  node [fontsize=10];",
        '  edge [fontsize=9, color="#64748b"];',
    ]
    processes: dict[str, list[str]] = defaultdict(list)
    for name, component in spec.components.items():
        processes[component.process].append(name)
    for process, members in processes.items():
        lines.append(
            f"  subgraph {q(f'cluster_p_{process}')} {{ label={q(f'{process} process')}; "
            'style="rounded"; color="#94a3b8";'
        )
        for member in members:
            lines.append(
                f"    subgraph {q(f'cluster_c_{member}')} {{ label={q(member)}; "
                'style="rounded,filled"; fillcolor="#f1f5f9"; color="#cbd5e1";'
            )
            owned = [e.name for e in spec.entities.values() if e.owner == member]
            entity_style = 'shape=ellipse, style=filled, fillcolor="#dbeafe", color="#3b82f6"'
            lines.extend(f"      {q(entity)} [{entity_style}];" for entity in owned)
            if not owned:
                lines.append(f"      {q(f'anchor_{member}')} [shape=point, style=invis];")
            lines.append("    }")
        lines.append("  }")
    for boundary in spec.boundaries.values():
        node = q(f"b_{boundary.name}")
        lines.append(
            f'  {node} [label={q(boundary.name)}, shape=hexagon, style=filled, fillcolor="#fef3c7", color="#d97706"];'
        )
        sender = next(
            (e.name for e in spec.entities.values() if e.owner == boundary.sender), f"anchor_{boundary.sender}"
        )
        receiver = next(
            (e.name for e in spec.entities.values() if e.owner == boundary.receiver), f"anchor_{boundary.receiver}"
        )
        lines.append(f"  {q(sender)} -> {node} [ltail={q(f'cluster_c_{boundary.sender}')}];")
        lines.append(f"  {node} -> {q(receiver)} [lhead={q(f'cluster_c_{boundary.receiver}')}];")
    lines.append("}")
    return dot_svg("\n".join(lines))
