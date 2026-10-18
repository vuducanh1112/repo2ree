"""Human views of a check: verdicts first, then the spec drawn with what was exercised."""

from __future__ import annotations

import json

from repo2ree_conformance.check import INITIAL, CheckResult
from repo2ree_conformance.spec import Spec

MARK = {
    "passed": "✅ passed",
    "violated": "❌ violated",
    "inconclusive": "⚠️ inconclusive",
    "not_triggered": "∅ not triggered",
}
FINDING_LIMIT = 20


def state_chart(spec: Spec, result: CheckResult, entity: str) -> str:
    """The declared machine; each edge is labelled with how often the evidence took it."""
    machine = spec.entities[entity]
    counts = result.coverage.transitions.get(entity, {})
    lines = ["```mermaid", "stateDiagram-v2"]
    lines.extend(f"    [*] --> {state}: {counts.get(f'{INITIAL} -> {state}', 0)}" for state in machine.initial)
    for source, targets in machine.edges.items():
        lines.extend(
            f"    {source} --> {target}: {counts.get(f'{source} -> {target}', 0)}" for target in sorted(targets)
        )
    lines.extend(f"    {state} --> [*]" for state in machine.terminal)
    lines.append("```")
    return "\n".join(lines)


def render_markdown(spec: Spec, result: CheckResult) -> str:
    lines = [
        "# Behaviour conformance",
        "",
        f"**Verdict: {MARK[result.verdict]}** against specification `{result.spec_digest}`.",
        "",
        "## Rules",
        "",
        "| Rule | Verdict | Triggered | Open | Findings |",
        "|---|---|---:|---:|---:|",
    ]
    lines += [
        f"| `{rule.rule}` | {MARK[rule.verdict]} | {rule.triggered} | {rule.open} | {len(rule.findings)} |"
        for rule in result.rules
    ]
    for rule in result.rules:
        if not rule.findings:
            continue
        lines += ["", f"### `{rule.rule}`", "", rule.summary, ""]
        for finding in rule.findings[:FINDING_LIMIT]:
            refs = ", ".join(f"`{ref}`" for ref in finding.evidence)
            lines.append(
                f"- **{finding.verdict}** · {finding.subject}: {finding.reason}" + (f" ({refs})" if refs else "")
            )
        if len(rule.findings) > FINDING_LIMIT:
            lines.append(f"- … {len(rule.findings) - FINDING_LIMIT} more")
    lines += ["", "## Sources", "", "| Source | Kind | Complete | Closed | Problems |", "|---|---|---|---|---|"]
    lines += [
        f"| `{source.id}` | {source.kind} | {'yes' if source.complete else 'no'} | "
        f"{'yes' if source.closed else 'no'} | {'; '.join(source.problems) or '—'} |"
        for source in result.sources
    ]
    lines += ["", "## Coverage", "", "Edges labelled `0` are declared behaviour no evidence exercised.", ""]
    for entity in sorted(spec.entities):
        gaps = [edge for edge, count in result.coverage.transitions.get(entity, {}).items() if not count]
        lines += [f"### {entity}", "", state_chart(spec, result, entity), ""]
        if gaps:
            lines += [f"Unexercised: {', '.join(f'`{edge}`' for edge in gaps)}", ""]
    for boundary, counts in sorted(result.coverage.messages.items()):
        lines += [f"### Boundary `{boundary}`", "", "| Message | Observed |", "|---|---:|"]
        lines += [f"| `{message}` | {count} |" for message, count in counts.items()]
        lines.append("")
    return "\n".join(lines)


def render_json(result: CheckResult) -> str:
    document = result.model_dump(mode="json")
    document["verdict"] = result.verdict
    for rule, dumped in zip(result.rules, document["rules"], strict=True):
        dumped["verdict"] = rule.verdict
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
