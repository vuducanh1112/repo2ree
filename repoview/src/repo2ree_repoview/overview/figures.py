"""Generated diagrams, copied into the bundle with the commit each was drawn from."""

from __future__ import annotations

from pathlib import Path

from repo2ree_repoview.overview.html import esc
from repo2ree_repoview.overview.inputs import (
    DIAGRAMS,
    Bundle,
)
from repo2ree_repoview.stamp import read_svg_stamp


def diagram_origin(bundle: Bundle, path: Path) -> str:
    """Which commit a diagram was generated from, as it records itself, against the overview's commit."""
    stamp = read_svg_stamp(path) if path.suffix == ".svg" else None
    if stamp is None:
        return '<span class="state-stale">Records no commit; regenerate it.</span>'
    revision = f"<code>{esc(stamp['revision'][:10])}</code>" + (" with uncommitted changes" if stamp["dirty"] else "")
    if stamp["revision"] != bundle.revision:
        older = f"Generated from an older commit, {revision}, at {esc(stamp['generated'])}."
        return f'<span class="state-stale">{older}</span>'
    return f"Generated from {revision} at {esc(stamp['generated'])}."


def diagram(bundle: Bundle, path: Path, title: str, note: str = "") -> str:
    """A generated diagram, copied into the bundle so the page keeps it."""
    origin = (read_svg_stamp(path) or {}) if path.is_file() and path.suffix == ".svg" else {}
    relative = bundle.copy(
        path, f"diagrams/{path.relative_to(DIAGRAMS)}", kind="diagram", revision=str(origin.get("revision", ""))
    )
    if relative is None:
        return f'<h3>{esc(title)}</h3><p class="state-missing">Missing: run <code>just generate-diagrams</code>.</p>'
    return (
        f'<h3>{esc(title)}</h3><p class="muted">{note} {diagram_origin(bundle, path)} '
        f'<a href="{esc(relative)}">Open full size</a></p>'
        f'<div class="diagram"><img src="{esc(relative)}" alt="{esc(title)}" loading="lazy"></div>'
    )
