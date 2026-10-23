"""A self-contained HTML assurance report: verdicts first, then the system and its machines drawn.

Per-REE views of the evidence (operations, sequences, step standings) are drawn by repo2ree_assurance_traceview.
"""

from __future__ import annotations

from html import escape

from repo2ree_assurance_checker.check import INITIAL, CheckResult
from repo2ree_assurance_checker.report import describe_extra, stamped
from repo2ree_assurance_checker.spec import Spec
from repo2ree_assurance_checker.views import system_map

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"
LABELS = {"passed": "passed", "violated": "violated", "inconclusive": "inconclusive", "not_triggered": "not triggered"}

STYLE = """
:root { --bg:#fbfaf8; --fg:#1d1d1b; --muted:#6b6a66; --line:#e4e1db; --card:#ffffff;
  --ok:#2f7d4f; --bad:#b3261e; --warn:#9a6700; --idle:#8a8780;
 }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#171716; --fg:#ecebe7; --muted:#a3a19b; --line:#2f2e2b; --card:#1f1f1d;
  --ok:#6cc58f; --bad:#f2847b; --warn:#e5b54a; --idle:#8a8780;
 } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:24px; margin:0 0 4px; }
h2 { font-size:18px; margin:36px 0 10px; }
h3 { font-size:15px; margin:20px 0 8px; }
.muted { color:var(--muted); } code { font-size:13px; }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-weight:600; font-size:13px; }
.passed { color:var(--ok); } .violated { color:var(--bad); }
.inconclusive { color:var(--warn); } .not_triggered { color:var(--idle); }
.badge.passed { background:color-mix(in srgb, var(--ok) 14%, transparent); }
.badge.violated { background:color-mix(in srgb, var(--bad) 14%, transparent); }
.badge.inconclusive { background:color-mix(in srgb, var(--warn) 16%, transparent); }
table { border-collapse:collapse; width:100%; background:var(--card); border:1px solid var(--line); }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-weight:600; font-size:13px; color:var(--muted); }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.scroll { overflow-x:auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; overflow-x:auto; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:12px; }
ul.findings { padding-left:18px; } ul.findings li { margin:4px 0; }
details summary { cursor:pointer; color:var(--muted); }
"""


def _badge(verdict: str) -> str:
    return f'<span class="badge {verdict}">{LABELS[verdict]}</span>'


def _mermaid(source: str) -> str:
    return f'<pre class="mermaid">{escape(source)}</pre>'


def _state_chart(spec: Spec, result: CheckResult, entity: str) -> str:
    machine = spec.entities[entity]
    counts = result.coverage.transitions.get(entity, {})
    lines = ["stateDiagram-v2"]
    if not machine.constrained:
        # Any move between its states is allowed: there are no edges to draw or count.
        lines.extend(f"    {state}" for state in machine.states)
    else:
        lines.extend(f"    [*] --> {state}: {counts.get(f'{INITIAL} -> {state}', 0)}" for state in machine.initial)
        for source, targets in machine.edges.items():
            lines.extend(
                f"    {source} --> {target}: {counts.get(f'{source} -> {target}', 0)}" for target in sorted(targets)
            )
        lines.extend(f"    {state} --> [*]" for state in machine.terminal)
    return "\n".join(lines)


def render_html(spec: Spec, result: CheckResult) -> str:
    parts: list[str] = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Behaviour Assurance</title><style>{STYLE}</style></head><body><main>",
        "<h1>Behaviour assurance</h1>",
        (
            f"<p>{_badge(result.verdict)} <span class='muted'>against specification "
            f"<code>{escape(result.spec_digest)}</code>, vocabulary "
            f"<code>{escape(result.vocabulary_digest)}</code></span></p>"
        ),
    ]
    findings = [(rule, finding) for rule in result.rules for finding in rule.findings]
    parts.append("<h2>Findings</h2>")
    if findings:
        parts.append("<ul class='findings'>")
        for verdict in ("violated", "inconclusive"):
            for rule, finding in findings:
                if finding.verdict != verdict:
                    continue
                refs = " ".join(f"<code>{escape(ref)}</code>" for ref in finding.evidence)
                parts.append(
                    f"<li><span class='{verdict}'>{verdict}</span> · <code>{escape(rule.rule)}</code> · "
                    f"{escape(finding.subject)}: {escape(finding.reason)} <span class='muted'>{refs}</span></li>"
                )
        parts.append("</ul>")
    else:
        parts.append("<p class='muted'>None.</p>")
    parts += [
        (
            "<h2>Rules</h2><div class='scroll'><table><tr><th>Rule</th><th>Verdict</th><th>Triggered</th>"
            "<th>Open</th><th>Summary</th></tr>"
        )
    ]
    parts += [
        f"<tr><td><code>{escape(rule.rule)}</code></td><td>{_badge(rule.verdict)}</td>"
        f"<td class='num'>{rule.triggered}</td><td class='num'>{rule.open}</td><td>{escape(rule.summary)}</td></tr>"
        for rule in result.rules
    ]
    parts.append("</table></div>")
    parts += [
        (
            "<h2>System</h2><p class='muted'>Processes, the components they host, the entities each component owns, "
            "boundaries (thick) and cross-entity invariants (dashed). Drawn from the specification.</p>"
        ),
        f"<div class='card'>{_mermaid(system_map(spec))}</div>",
    ]
    parts.append(
        "<p class='muted'>Each REE's operations, how they travel across components, and its step evidence: "
        "<code>just trace-dossier [dossier]</code>, from this check's verification.json.</p>"
    )
    parts.append(
        "<h2>State machines</h2><p class='muted'>Edge labels count observed transitions; 0 is declared "
        "behaviour no evidence exercised.</p><div class='grid'>"
    )
    for entity in sorted(spec.entities):
        parts.append(
            f"<div class='card'><h3>{escape(entity)}</h3>"
            f"<p class='muted'>{escape(spec.entities[entity].summary)}</p>"
            f"{_mermaid(_state_chart(spec, result, entity))}</div>"
        )
    parts.append("</div><h2>Boundaries</h2>")
    for boundary, counts in sorted(result.coverage.messages.items()):
        parts.append(f"<h3>{escape(boundary)}</h3><table><tr><th>Message</th><th>Observed</th></tr>")
        parts += [f"<tr><td><code>{escape(m)}</code></td><td class='num'>{c}</td></tr>" for m, c in counts.items()]
        parts.append("</table>")
    parts.append(
        "<h2>Sources</h2><div class='scroll'><table><tr><th>Source</th><th>Kind</th><th>Complete</th><th>Closed</th>"
        "<th>Vocabulary</th><th>Problems</th></tr>"
    )
    parts += [
        f"<tr><td><code>{escape(source.id)}</code></td><td>{source.kind}</td><td>{'yes' if source.complete else 'no'}"
        f"</td><td>{'yes' if source.closed else 'no'}</td><td>{escape(stamped(source, result))}</td>"
        f"<td>{escape('; '.join(source.problems)) or '—'}</td></tr>"
        for source in result.sources
    ]
    parts.append("</table></div>")
    if result.extras:
        parts.append(
            "<h2>Not judged</h2><p class='muted'>Recorded beyond the vocabulary; the owners' own, never part of "
            "a verdict.</p><ul>"
        )
        parts += [
            f"<li>{escape(describe_extra(extra).replace('`', ''))}: {extra.count} records "
            f"<span class='muted'>{' '.join(f'<code>{escape(ref)}</code>' for ref in extra.evidence)}</span></li>"
            for extra in result.extras
        ]
        parts.append("</ul>")
    parts += [
        "</main>",
        "<script type='module'>",
        f"import mermaid from '{MERMAID}';",
        "const dark = matchMedia('(prefers-color-scheme: dark)').matches;",
        "mermaid.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'neutral', securityLevel: 'strict' });",
        "document.querySelectorAll('details')",
        "  .forEach(d => d.addEventListener('toggle', () => mermaid.run(), { once: true }));",
        "mermaid.run();",
        "</script></body></html>",
    ]
    return "\n".join(parts)
