"""What each gate needs for HEAD, tier by tier and platform by platform, and what proves it."""

from __future__ import annotations

from repo2ree_repoview.overview.html import Page, esc, section, table
from repo2ree_repoview.overview.receipt import TierNeed, TierReceipt, gate_needs, tier_receipts
from repo2ree_repoview.repository import Head


def _state(need: TierNeed) -> str:
    if need.current is not None:
        return '<span class="state-current">current</span>'
    if need.last is not None:
        last = esc((need.last.revision or "?")[:10])
        return f'<span class="state-stale">stale</span> <span class="muted">last {last}</span>'
    return '<span class="state-missing">missing</span>'


def _proof(receipt: TierReceipt | None) -> str:
    if receipt is None:
        return '<span class="muted">none</span>'
    skipped = f", {receipt.skipped} skipped" if receipt.skipped else ""
    judged = ", behaviour judged" if receipt.judged else ""
    return f"<code>{esc(receipt.run)}</code> on {esc(receipt.machine)}: {receipt.tests} tests{skipped}{judged}"


def receipts_section(head: Head) -> str:
    needs = gate_needs(head, tier_receipts())
    if not needs:
        return section("receipts", "Receipts", "No gate policy in this checkout (scripts/gates/policy.toml).", "")
    body = []
    for gate, gate_needs_ in needs.items():
        rows = [
            [
                esc(need.tier),
                esc(need.place),
                _state(need),
                _proof(need.current or need.last),
                f"<code>just {esc(need.recipe)}</code>" if need.current is None and need.recipe else "",
            ]
            for need in gate_needs_
        ]
        body.append(f"<h3>{esc(gate)}</h3>")
        body.append(table(["Tier", "Where", "State", "Proof", "To prove it"], rows))
    lede = (
        f"Tier receipts for HEAD's tree <code>{esc(head.tree[:12])}</code>, as each gate's policy asks for them"
        " (<code>scripts/gates/policy.toml</code>). A run certifies only from a clean tree, whole, on the"
        " policy's deployment; another machine's receipts count once they are brought back."
        " <code>just gate-plan &lt;gate&gt;</code> prints the same from a terminal."
    )
    return section("receipts", "Receipts", lede, "".join(body))


def page_receipts(head: Head) -> Page:
    needs = gate_needs(head, tier_receipts())
    proven = sum(need.current is not None for gate in needs.values() for need in gate)
    total = sum(len(gate) for gate in needs.values())
    return Page("receipts", "Receipts", f"{proven} of {total} tier receipts current for HEAD", receipts_section(head))
