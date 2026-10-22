"""Render the declared Just recipe dependency graph.

Edges follow execution order: prerequisites point to the recipe that consumes
them, while subsequent dependencies point away from the recipe whose body runs
first. Recipes with no incoming execution edge share the first rank.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field, JsonValue, ValidationError

from repo2ree_repoview.diagrams import emit
from repo2ree_repoview.documents import Document
from repo2ree_repoview.graphviz import inline_svg, quote
from repo2ree_repoview.repository import ROOT

PALETTE = (
    "#dbeafe",
    "#dcfce7",
    "#fef3c7",
    "#f3e8ff",
    "#fee2e2",
    "#cffafe",
    "#e2e8f0",
)


class _Named(Document):
    name: str


class _Dependency(Document):
    recipe: str


class _Recipe(Document):
    attributes: tuple[JsonValue, ...] = ()
    body: tuple[JsonValue, ...] = ()
    dependencies: tuple[_Dependency, ...] = ()
    doc: str | None = None
    parameters: tuple[_Named, ...] = ()
    priors: int | None = None
    private: bool = False

    @property
    def group(self) -> str:
        for attribute in self.attributes:
            if isinstance(attribute, dict) and isinstance(attribute.get("group"), str):
                return str(attribute["group"])
        return "Ungrouped"


class _Dump(Document):
    recipes: dict[str, _Recipe] = Field(default_factory=dict)


@dataclass(frozen=True)
class Dependency:
    recipe: str
    subsequent: bool = False


@dataclass(frozen=True)
class Recipe:
    name: str
    group: str
    private: bool
    has_body: bool
    dependencies: tuple[Dependency, ...]
    doc: str = ""
    parameters: tuple[str, ...] = ()

    @property
    def aggregate(self) -> bool:
        return bool(self.dependencies) and not self.has_body


def parse_recipes(document: dict[str, Any]) -> dict[str, Recipe]:
    """Convert Just's JSON dump into the small model the diagram and the overview draw."""
    return _recipes(_Dump.model_validate(document))


def _recipes(dump: _Dump) -> dict[str, Recipe]:
    parsed: dict[str, Recipe] = {}
    for name, raw in dump.recipes.items():
        priors = len(raw.dependencies) if raw.priors is None else raw.priors
        parsed[name] = Recipe(
            name=name,
            group=raw.group,
            private=raw.private,
            has_body=bool(raw.body),
            dependencies=tuple(
                Dependency(dependency.recipe, subsequent=index >= priors)
                for index, dependency in enumerate(raw.dependencies)
            ),
            doc=raw.doc or "",
            parameters=tuple(parameter.name for parameter in raw.parameters),
        )
    return parsed


def load_recipes() -> dict[str, Recipe]:
    dump = subprocess.run(
        ["just", "--dump", "--dump-format", "json"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    return _recipes(_Dump.model_validate_json(dump))


def dependency_closure(recipes: dict[str, Recipe], root: str) -> set[str]:
    if root not in recipes:
        raise ValueError(f"unknown Just recipe: {root}")
    selected: set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        pending.extend(dependency.recipe for dependency in recipes[name].dependencies)
    return selected


def execution_edges(recipes: dict[str, Recipe]) -> set[tuple[str, str, bool]]:
    edges: set[tuple[str, str, bool]] = set()
    for recipe in recipes.values():
        for dependency in recipe.dependencies:
            if dependency.subsequent:
                edges.add((recipe.name, dependency.recipe, True))
            else:
                edges.add((dependency.recipe, recipe.name, False))
    return edges


def render_dot(recipes: dict[str, Recipe], *, root: str = "") -> str:
    selected = dependency_closure(recipes, root) if root else set(recipes)
    visible = {name: recipe for name, recipe in recipes.items() if name in selected}
    edges = {edge for edge in execution_edges(visible) if edge[0] in visible and edge[1] in visible}
    incoming = {head for _, head, _ in edges}
    sources = sorted(set(visible) - incoming)
    groups = sorted({recipe.group for recipe in visible.values()})
    colors = {group: PALETTE[index % len(PALETTE)] for index, group in enumerate(groups)}

    lines = [
        "digraph just_recipes {",
        "  rankdir=LR;",
        "  newrank=true;",
        '  graph [ranksep=0.9, nodesep=0.35, pad=0.3, fontname="Helvetica"];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,',
        '        color="#64748b", fontcolor="#172033", margin="0.14,0.08"];',
        '  edge [color="#94a3b8", arrowsize=0.7, penwidth=1.1, fontname="Helvetica", fontsize=8];',
        "",
    ]
    for name, recipe in sorted(visible.items()):
        styles = ["rounded", "filled"]
        if recipe.private:
            styles.append("dashed")
        attributes = [
            f"label={quote(name)}",
            f"fillcolor={quote(colors[recipe.group])}",
            f"style={quote(','.join(styles))}",
            f"tooltip={quote(recipe.group)}",
        ]
        if recipe.aggregate:
            attributes.append("penwidth=2.2")
        if name == root:
            attributes.extend(['color="#0f766e"', "penwidth=3.0"])
        lines.append(f"  {quote(name)} [{', '.join(attributes)}];")
    if sources:
        joined = "; ".join(quote(name) for name in sources)
        lines.extend(["", f"  {{ rank=source; {joined}; }}"])
    if edges:
        lines.append("")
    for tail, head, subsequent in sorted(edges):
        edge_attributes = ' [style=dashed, label="after", color="#a78bfa"]' if subsequent else ""
        lines.append(f"  {quote(tail)} -> {quote(head)}{edge_attributes};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="", help="draw only this recipe and its declared dependencies")
    parser.add_argument("-f", "--format", choices=("svg", "dot"), default="svg")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    try:
        dot_source = render_dot(load_recipes(), root=args.root)
        emit(inline_svg(dot_source, css_class="just-recipe-graph") if args.format == "svg" else dot_source, args.output)
    except (OSError, ValueError, ValidationError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
