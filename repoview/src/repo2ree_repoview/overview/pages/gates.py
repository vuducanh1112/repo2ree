"""What the last assurance gate accepted, and what its receipt concedes."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.html import Page, esc, in_frame, section, table
from repo2ree_repoview.overview.receipt import Evidence, Receipt, reached

# The behaviour trace of a whole dossier, beside the one of each REE (repo2ree_assurance_traceview's).
DOSSIER_PAGE = "dossier.html"
SLUG = "assurance-gate"


def evidence_links(bundle: Bundle, directory: str | None) -> str:
    """Links to a test's bundled verdict report and its behaviour traces: one link, to the whole dossier's page
    where there is one, whose tabs lead to each REE's."""
    if directory is None:
        return '<span class="muted">not bundled</span>'
    links = []
    if (bundle.root / directory / "verification/assurance.html").is_file():
        links.append(f'<a href="{esc(in_frame(f"{directory}/verification/assurance.html", SLUG))}">verdicts</a>')
    pages = sorted((bundle.root / directory / "traces").glob("*.html"))
    whole = next((page for page in pages if page.name == DOSSIER_PAGE), None)
    traces = [page for page in pages if page is not whole]
    if traces:
        label = "trace" if len(traces) == 1 else f"traces · {len(traces)} REEs"
        shown = in_frame(f"{directory}/traces/{(whole or traces[0]).name}", SLUG)
        links.append(f'<a href="{esc(shown)}">{label}</a>')
    return " · ".join(links) or '<span class="muted">none</span>'


def page_gates(receipt: Receipt | None, unreached: dict[str, str], bundle: Bundle, evidence: Evidence) -> Page:
    tests = len(receipt.tests) if receipt else 0
    teaser = f"{tests} tests in the last receipt; {reached(receipt)} specified items reached"
    return Page(SLUG, "Assurance gate", teaser, gates_section(receipt, unreached, bundle, evidence))


def gates_section(receipt: Receipt | None, unreached: dict[str, str], bundle: Bundle, evidence: Evidence) -> str:
    if receipt is None:
        return section(
            "assurance-gate",
            "Assurance gate",
            "No assurance-gate receipt in this clone yet: run <code>just assurance-gate</code>.",
            "",
        )
    rows = [
        [
            esc(t.test),
            esc(t.outcome),
            f'<span class="{"ok" if t.behaviour == "passed" else "ex"}">{esc(t.behaviour)}</span>',
            esc(t.excused or ""),
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
    lede = "What the last assurance gate accepted, and what its receipt concedes."
    return section("assurance-gate", "Assurance gate", lede, body)
