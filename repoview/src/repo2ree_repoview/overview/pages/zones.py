"""What each part of the repository is for, and which parts humans review."""

from __future__ import annotations

from repo2ree_repoview.overview.exports import Zones
from repo2ree_repoview.overview.html import Page, esc, filter_box, prose, section


def page_zones(declared: Zones) -> Page:
    parts = []
    for zone in declared.zones:
        badge = '<span class="badge protected">protected</span>' if zone.protected else ""
        groups = "".join(
            f'<div class="group"><b>{esc(g.name)}</b> <span class="muted">{esc(g.summary)}</span>'
            + "".join(
                f'<div class="entry" data-row><code>{esc(e.path)}</code><span>{prose(e.description)}</span></div>'
                for e in g.entries
            )
            + "</div>"
            for g in zone.groups
        )
        parts.append(
            f'<div class="zone{" is-protected" if zone.protected else ""}" id="zone-{esc(zone.name)}">'
            f'<h3><span class="dot zone-{esc(zone.name)}"></span>{esc(zone.name)} {badge}</h3>'
            f'<div class="muted">{esc(zone.summary)}</div>{groups}</div>'
        )
    warn = "".join(f'<p class="state-missing">! {esc(p)}</p>' for p in declared.problems)
    lede = (
        "Every tracked file belongs to the zone of its longest matching entry in <code>zones.toml</code>. "
        "Protected zones are what humans review; a commit touching one touches nothing else."
    )
    body = section(
        "zones",
        "Zones",
        lede,
        filter_box("zone-list", "Filter paths and descriptions…") + f'<div id="zone-list">{"".join(parts)}</div>{warn}',
    )
    protected = sum(len(zone.entries) for zone in declared.zones if zone.protected)
    return Page("zones", "Zones", f"{len(declared.zones)} zones; {protected} protected entries humans review", body)
