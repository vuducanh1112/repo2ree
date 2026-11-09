"""What the last assurance gate accepted, and what its receipt concedes."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.html import Page, esc, in_frame, section, table
from repo2ree_repoview.overview.receipt import Evidence, Receipt, ReceiptTest, reached

# The behaviour trace of a whole dossier, beside the one of each REE (repo2ree_assurance_traceview's).
DOSSIER_PAGE = "dossier.html"
SLUG = "assurance-gate"


def evidence_links(bundle: Bundle, directory: str | None, origin: str = SLUG) -> str:
    """Links to a test's bundled verdict report and its behaviour traces: one link, to the whole dossier's page
    where there is one, whose tabs lead to each REE's."""
    if directory is None:
        return '<span class="muted">not bundled</span>'
    links = []
    if (bundle.root / directory / "verification/assurance.html").is_file():
        links.append(f'<a href="{esc(in_frame(f"{directory}/verification/assurance.html", origin))}">verdicts</a>')
    pages = sorted((bundle.root / directory / "traces").glob("*.html"))
    whole = next((page for page in pages if page.name == DOSSIER_PAGE), None)
    traces = [page for page in pages if page is not whole]
    if traces:
        label = "trace" if len(traces) == 1 else f"traces · {len(traces)} REEs"
        shown = in_frame(f"{directory}/traces/{(whole or traces[0]).name}", origin)
        links.append(f'<a href="{esc(shown)}">{label}</a>')
    return " · ".join(links) or '<span class="muted">none</span>'


def judged_now(test: ReceiptTest, judged: dict[tuple[str, str], str] | None) -> str:
    """What this tree's checker makes of a certified test's evidence, said only where it differs."""
    found = (judged or {}).get((test.run, test.test))
    if found is None:
        return '<span class="muted">not assessed: run <code>just assess-behaviour</code></span>'
    if found == test.behaviour:
        return '<span class="muted">agrees</span>'
    return f'<span class="no">{esc(found)}</span>'


def page_gates(
    receipt: Receipt | None,
    unreached: dict[str, str],
    bundle: Bundle,
    evidence: Evidence,
    judged: dict[tuple[str, str], str] | None,
) -> Page:
    tests = len(receipt.tests) if receipt else 0
    teaser = f"{tests} tests in the last receipt; {reached(receipt)} specified items reached"
    return Page(SLUG, "Assurance gate", teaser, gates_section(receipt, unreached, bundle, evidence, judged))


def gates_section(
    receipt: Receipt | None,
    unreached: dict[str, str],
    bundle: Bundle,
    evidence: Evidence,
    judged: dict[tuple[str, str], str] | None,
) -> str:
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
            judged_now(t, judged),
            esc(t.excused or ""),
            evidence_links(bundle, evidence.tests.get((t.run, t.test))),
        ]
        for t in receipt.tests
    ]
    now = judged or {}
    differ = sum(t.behaviour != now[(t.run, t.test)] for t in receipt.tests if (t.run, t.test) in now)
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
        + "</p><p>Each test's evidence is judged and drawn again by this tree's checker and traceview "
        "(<code>just visualize-behaviour</code>); the verdicts and traces linked here are those. "
        + (
            "None has been yet."
            if judged is None
            else f'<span class="no">{differ} tests</span> are judged differently than the receipt certified them: '
            "the gate would decide them differently now."
            if differ
            else "It agrees with every verdict the receipt certified."
        )
        + "</p>"
        + table(["Test", "Outcome", "Behaviour", "This tree's checker", "Excused because", "Evidence"], rows)
        + f"<h3>What a receipt does not prove ({len(unreached)} items)</h3>"
        + table(["Unreached by any gated test", "Why"], unreached_rows)
    )
    lede = "What the last assurance gate accepted, and what its receipt concedes."
    return section("assurance-gate", "Assurance gate", lede, body)
