"""What the last behaviour gate accepted, and what its receipt concedes."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from repo2ree_repoview.overview.html import esc, section, table
from repo2ree_repoview.overview.inputs import (
    Bundle,
)


def evidence_links(bundle: Bundle, directory: str | None) -> str:
    """Links to a test's bundled verdict report and operation traces."""
    if directory is None:
        return '<span class="muted">not bundled</span>'
    links = []
    if (bundle.root / directory / "verification/conformance.html").is_file():
        links.append(f'<a href="{esc(directory)}/verification/conformance.html">verdicts</a>')
    traces = sorted((bundle.root / directory / "traces").glob("*.html"))
    links += [f'<a href="{esc(directory)}/traces/{esc(trace.name)}">trace</a>' for trace in traces]
    return " · ".join(links) or '<span class="muted">none</span>'


def page_gates(
    receipt: dict[str, Any] | None,
    unreached: dict[str, str],
    bundle: Bundle,
    tests: dict[tuple[str, str], str],
) -> str:
    if not receipt:
        return section(
            "behaviour-gate",
            "Behaviour gate",
            "No behaviour receipt in this clone yet: run <code>just behaviour-gate</code>.",
            "",
        )
    rows = [
        [
            esc(t["test"]),
            esc(t["outcome"]),
            f'<span class="{"ok" if t["behaviour"] == "passed" else "ex"}">{esc(t["behaviour"])}</span>',
            esc(t.get("excused", "")),
            evidence_links(bundle, tests.get((t["run"], t["test"]))),
        ]
        for t in receipt.get("tests", [])
    ]
    coverage = receipt.get("coverage", {})
    reasons: dict[str, list[str]] = defaultdict(list)
    for item, reason in unreached.items():
        reasons[reason].append(item)
    unreached_rows = [
        [" ".join(f"<code>{esc(i)}</code>" for i in items), esc(reason)] for reason, items in reasons.items()
    ]
    body = (
        f"<p>Receipt for <code>{esc(receipt.get('revision', '')[:10])}</code> from runs "
        + ", ".join(f"<code>{esc(Path(r).name)}</code>" for r in receipt.get("runs", []))
        + ", copied into this overview under <code>evidence/</code>"
        + (
            f". The suite reached {coverage.get('reached', '?')} of {coverage.get('declared', '?')} "
            "specified rules, edges, and messages."
            if coverage
            else "."
        )
        + "</p>"
        + table(["Test", "Outcome", "Behaviour", "Excused because", "Evidence"], rows)
        + f"<h3>What a receipt does not prove ({len(unreached)} items)</h3>"
        + table(["Unreached by any gated test", "Why"], unreached_rows)
    )
    lede = "What the last behaviour gate accepted, and what its receipt concedes."
    return section("behaviour-gate", "Behaviour gate", lede, body)
