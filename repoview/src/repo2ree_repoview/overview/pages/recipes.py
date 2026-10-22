"""The Just recipes and their dependency graph."""

from __future__ import annotations

from repo2ree_repoview.diagrams.recipes import Recipe
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.figures import DIAGRAMS, diagram
from repo2ree_repoview.overview.html import Page, esc, filter_box, section, table


def page_recipes(recipes: dict[str, Recipe], bundle: Bundle) -> Page:
    listed = sorted(recipes.values(), key=lambda r: (r.group, r.name))
    rows = [
        [
            f"<code>{esc(r.name)}</code>" + (' <span class="badge">private</span>' if r.private else ""),
            esc(r.group),
            esc(r.doc),
            " ".join(f"<code>{esc(p)}</code>" for p in r.parameters),
            " ".join(f"<code>{esc(d.recipe)}</code>" for d in r.dependencies),
        ]
        for r in listed
    ]
    public = sum(not r.private for r in listed)
    body = filter_box("recipe-table", "Filter recipes…") + table(
        ["Recipe", "Group", "What it does", "Parameters", "Runs first"], rows, "recipe-table"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "just-recipes.svg",
        "Recipe dependency graph",
        "Prerequisites point to the recipe that consumes them.",
    )
    lede = f"{public} public recipes and {len(listed) - public} private ones, from <code>just --dump</code>."
    body = section("just-recipes", "Just recipes", lede, body)
    return Page("just-recipes", "Just recipes", f"{public} public recipes", body)
