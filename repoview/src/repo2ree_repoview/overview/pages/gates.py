"""What the last behaviour gate accepted, and what its receipt concedes."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.html import Page, esc, section, table
from repo2ree_repoview.overview.receipt import Evidence, Receipt, reached


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


def page_gates(receipt: Receipt | None, unreached: dict[str, str], bundle: Bundle, evidence: Evidence) -> Page:
    tests = len(receipt.tests) if receipt else 0
    teaser = f"{tests} tests in the last receipt; {reached(receipt)} specified items reached"
    return Page("behaviour-gate", "Behaviour gate", teaser, gates_section(receipt, unreached, bundle, evidence))


def gates_section(receipt: Receipt | None, unreached: dict[str, str], bundle: Bundle, evidence: Evidence) -> str:
    if receipt is None:
        return section(
            "behaviour-gate",
            "Behaviour gate",
            "No behaviour receipt in this clone yet: run <code>just behaviour-gate</code>.",
            "",
        )
    rows = [
        [
            esc(t.test),
            esc(t.outcome),
            f'<span class="{"ok" if t.behaviour == "passed" else "ex"}">{esc(t.behaviour)}</span>',
            esc(t.excused),
            evidence_links(bundle, evidence.tests.get((t.run, t.test))),
        ]
        for t in receipt.tests
    ]
    reasons: dict[str, list[str]] = defaultdict(list)
    for item, reason in unreached.items():
        reasons[reason].append(item)
    unreached_rows = [
        [" ".join(f"<code>{esc(i)}</code>" for i in items), esc(reason)] for reason, items in reasons.items()
    ]
    body = (
        f"<p>Receipt for <code>{esc(receipt.revision[:10])}</code> from runs "
        + ", ".join(f"<code>{esc(Path(r).name)}</code>" for r in receipt.runs)
        + ", copied into this overview under <code>evidence/</code>"
        + (f". The suite reached {reached(receipt)} specified rules, edges, and messages." if receipt.coverage else ".")
        + "</p>"
        + table(["Test", "Outcome", "Behaviour", "Excused because", "Evidence"], rows)
        + f"<h3>What a receipt does not prove ({len(unreached)} items)</h3>"
        + table(["Unreached by any gated test", "Why"], unreached_rows)
    )
    lede = "What the last behaviour gate accepted, and what its receipt concedes."
    return section("behaviour-gate", "Behaviour gate", lede, body)
