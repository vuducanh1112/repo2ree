"""Generated diagrams, copied into the bundle with the commit each was drawn from."""

from __future__ import annotations

from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.html import esc
from repo2ree_repoview.repository import ROOT
from repo2ree_repoview.stamp import Stamp, read_svg_stamp, unstamp

DIAGRAMS = ROOT / "reports/diagrams"


def diagram_origin(bundle: Bundle, stamp: Stamp | None) -> str:
    """Which commit a diagram was generated from, as it records itself, against the overview's commit."""
    if stamp is None:
        return '<span class="state-stale">Records no commit; regenerate it.</span>'
    revision = f"<code>{esc(stamp.revision[:10])}</code>" + (" with uncommitted changes" if stamp.dirty else "")
    if stamp.revision != bundle.revision:
        older = f"Generated from an older commit, {revision}, at {esc(stamp.generated)}."
        return f'<span class="state-stale">{older}</span>'
    return f"Generated from {revision} at {esc(stamp.generated)}."


def diagram(bundle: Bundle, path: Path, title: str, note: str = "") -> str:
    """A generated diagram, copied into the bundle so the page keeps it."""
    stamp = read_svg_stamp(path) if path.is_file() and path.suffix == ".svg" else None
    origin = Origin(kind="diagram", revision=stamp.revision if stamp else "")
    relative = bundle.copy(path, f"diagrams/{path.relative_to(DIAGRAMS)}", origin)
    if relative is None:
        return f'<h3>{esc(title)}</h3><p class="state-missing">Missing: run <code>just generate-diagrams</code>.</p>'
    return (
        f'<h3>{esc(title)}</h3><p class="muted">{note} {diagram_origin(bundle, stamp)} '
        f'<a href="{esc(relative)}">Open full size</a></p>'
        f'<div class="diagram"><img src="{esc(relative)}" alt="{esc(title)}" loading="lazy"></div>'
    )


def inlined(bundle: Bundle, relative: str, recipe: str = "generate-spec-diagrams") -> str:
    """A drawing ``recipe`` wrote, copied into the bundle and drawn in the page, unstamped."""
    path = DIAGRAMS / relative
    stamp = read_svg_stamp(path) if path.is_file() else None
    if (
        bundle.copy(path, f"diagrams/{relative}", Origin(kind="diagram", revision=stamp.revision if stamp else ""))
        is None
    ):
        return f'<p class="state-missing">Missing: run <code>just {esc(recipe)}</code>.</p>'
    svg = unstamp(path.read_text(encoding="utf-8"))
    return svg[svg.index("<svg") :]
