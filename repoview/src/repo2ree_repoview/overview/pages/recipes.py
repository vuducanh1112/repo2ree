"""The Just recipes and their dependency graph."""

from __future__ import annotations

from typing import Any

from repo2ree_repoview.overview.figures import diagram
from repo2ree_repoview.overview.html import esc, filter_box, section, table
from repo2ree_repoview.overview.inputs import (
    DIAGRAMS,
    Bundle,
)


def page_recipes(listed: list[dict[str, Any]], bundle: Bundle) -> str:
    rows = [
        [
            f"<code>{esc(r['name'])}</code>" + (' <span class="badge">private</span>' if r["private"] else ""),
            esc(r["group"]),
            esc(r["doc"]),
            " ".join(f"<code>{esc(p)}</code>" for p in r["parameters"]),
            " ".join(f"<code>{esc(d)}</code>" for d in r["dependencies"]),
        ]
        for r in listed
    ]
    public = sum(not r["private"] for r in listed)
    body = filter_box("recipe-table", "Filter recipes…") + table(
        ["Recipe", "Group", "What it does", "Parameters", "Runs first"], rows, "recipe-table"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "just-recipes.svg",
        "Recipe dependency graph",
        "Prerequisites point to the recipe that consumes them.",
    )
    return section(
        "just-recipes",
        "Just recipes",
        f"{public} public recipes and {len(listed) - public} private ones, from <code>just --dump</code>.",
        body,
    )
