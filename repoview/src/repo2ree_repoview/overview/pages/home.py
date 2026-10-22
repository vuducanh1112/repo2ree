"""The landing page: the head, the certificates, the repository by zone, and the bundle's provenance."""

from __future__ import annotations

from collections import Counter, defaultdict

from repo2ree_repoview.overview.bundle import Manifest
from repo2ree_repoview.overview.exports import Zones
from repo2ree_repoview.overview.html import Page, esc, section
from repo2ree_repoview.overview.receipt import Certificate
from repo2ree_repoview.repository import Head


def page_overview(now: Head, found: list[Certificate]) -> str:
    cards = [
        ("HEAD", f"<code>{now.revision[:10]}</code>", esc(now.subject)),
        ("Branch", esc(now.branch), "working tree dirty" if now.dirty else "working tree clean"),
    ]
    cards += [
        (c.name, f'<span class="state-{c.state}">{c.state}</span>', f"{esc(c.detail)} · <code>{esc(c.recipe)}</code>")
        for c in found
    ]
    body = (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="muted">{d}</div></div>'
            for k, v, d in cards
        )
        + "</div>"
    )
    return section(
        "overview", "Overview", f"Generated from commit <code>{now.revision[:10]}</code> ({esc(now.committed)}).", body
    )


def file_tree(declared: Zones) -> str:
    """The repository's top level, alphabetically, each entry coloured by the zones of the files under it."""
    entries: dict[str, Counter[str]] = defaultdict(Counter)
    for placed in declared.files:
        top, separator, _ = placed.path.partition("/")
        entries[top + separator][placed.zone or "unclaimed"] += 1
    order = [zone.name for zone in declared.zones]
    rows = []
    names = sorted(entries, key=lambda name: name.lstrip(".").lower())
    for index, name in enumerate(names):
        zones = sorted(
            entries[name], key=lambda zone: (-entries[name][zone], order.index(zone) if zone in order else 99)
        )
        main = zones[0]
        branch = "└──" if index == len(names) - 1 else "├──"
        dots = "".join(f'<span class="dot zone-{esc(zone)}"></span>' for zone in zones)
        title = ", ".join(f"{zone} {entries[name][zone]}" for zone in zones)
        rows.append(
            f'<a class="tree-row" href="zones.html#zone-{esc(main)}" title="{esc(title)}">'
            f'<span class="branch">{branch}</span><span class="name zone-text-{esc(main)}">{esc(name)}</span>'
            f'<span class="dots">{dots}</span></a>'
        )
    legend = "".join(
        f'<a class="legend-item" href="zones.html#zone-{esc(zone.name)}">'
        f'<span class="dot zone-{esc(zone.name)}"></span>'
        f"{esc(zone.name)}{' (protected)' if zone.protected else ''}</a>"
        for zone in declared.zones
    )
    return (
        '<section><h2>Repository</h2><p class="lede">The top level, coloured by zone; a directory holding more '
        "than one zone shows a dot for each, largest first. "
        'The <a href="zones.html">Zones</a> page has the details.</p>'
        f'<div class="tree-legend">{legend}</div><div class="tree"><div class="tree-root">repo2ree/</div>'
        f"{''.join(rows)}</div></section>"
    )


def page_home(now: Head, found: list[Certificate], pages: list[Page], declared: Zones, manifest: Manifest) -> Page:
    cards = "".join(
        f'<a class="card link" href="{p.slug}.html"><div class="v">{esc(p.title)}</div>'
        f'<div class="muted">{p.teaser}</div></a>'
        for p in pages
    )
    body = (
        page_overview(now, found)
        + file_tree(declared)
        + f'<section><h2>Pages</h2><div class="cards">{cards}</div></section>'
        + page_provenance(manifest)
    )
    return Page("index", "Overview", "", body)


def page_provenance(manifest: Manifest) -> str:
    receipt = manifest.receipt_revision
    if receipt is None:
        evidence = "no behaviour receipt, so no test evidence"
    elif receipt == manifest.revision:
        evidence = "test evidence from the receipt for this same commit"
    else:
        evidence = (
            f'<span class="state-stale">test evidence from an older commit, <code>{esc(receipt[:10])}</code></span>'
        )
    tree = "with uncommitted changes" if manifest.dirty else "clean"
    return (
        '<section><h2>Provenance</h2><p class="lede">'
        f"Built from <code>{esc(manifest.revision[:10])}</code> ({tree}) at {esc(manifest.generated)}, "
        f"with {evidence}. Everything shown from outside the tree is copied into this folder; "
        'see <a href="manifest.json">manifest.json</a>.</p></section>'
    )
