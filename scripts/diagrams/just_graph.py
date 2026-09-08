#!/usr/bin/env python3
"""Render the declared Just recipe dependency graph.

Edges follow execution order: prerequisites point to the recipe that consumes
them, while subsequent dependencies point away from the recipe whose body runs
first. Recipes with no incoming execution edge share the first rank.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PALETTE = (
    "#dbeafe",
    "#dcfce7",
    "#fef3c7",
    "#f3e8ff",
    "#fee2e2",
    "#cffafe",
    "#e2e8f0",
)


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

    @property
    def aggregate(self) -> bool:
        return bool(self.dependencies) and not self.has_body


def _group(attributes: list[Any]) -> str:
    for attribute in attributes:
        if isinstance(attribute, dict) and isinstance(attribute.get("group"), str):
            return str(attribute["group"])
    return "Ungrouped"


def parse_recipes(document: dict[str, Any]) -> dict[str, Recipe]:
    """Convert Just's JSON dump into the small model needed for drawing."""
    parsed: dict[str, Recipe] = {}
    for name, raw in document.get("recipes", {}).items():
        dependencies = raw.get("dependencies", [])
        priors = int(raw.get("priors", len(dependencies)))
        parsed[name] = Recipe(
            name=name,
            group=_group(raw.get("attributes", [])),
            private=bool(raw.get("private", False)),
            has_body=bool(raw.get("body", [])),
            dependencies=tuple(
                Dependency(str(dependency["recipe"]), subsequent=index >= priors)
                for index, dependency in enumerate(dependencies)
            ),
        )
    return parsed


def load_recipes() -> dict[str, Recipe]:
    result = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_recipes(json.loads(result.stdout))


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


def _quoted(value: str) -> str:
    return json.dumps(value)


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
            f"label={_quoted(name)}",
            f"fillcolor={_quoted(colors[recipe.group])}",
            f"style={_quoted(','.join(styles))}",
            f"tooltip={_quoted(recipe.group)}",
        ]
        if recipe.aggregate:
            attributes.append("penwidth=2.2")
        if name == root:
            attributes.extend(['color="#0f766e"', "penwidth=3.0"])
        lines.append(f"  {_quoted(name)} [{', '.join(attributes)}];")
    if sources:
        joined = "; ".join(_quoted(name) for name in sources)
        lines.extend(["", f"  {{ rank=source; {joined}; }}"])
    if edges:
        lines.append("")
    for tail, head, subsequent in sorted(edges):
        edge_attributes = ' [style=dashed, label="after", color="#a78bfa"]' if subsequent else ""
        lines.append(f"  {_quoted(tail)} -> {_quoted(head)}{edge_attributes};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_svg(dot_source: str) -> str:
    svg = subprocess.run(["dot", "-Tsvg"], input=dot_source, capture_output=True, text=True, check=True).stdout
    svg = svg[svg.index("<svg") :]
    return re.sub(
        r'width="[\d.]+pt" height="[\d.]+pt"',
        'class="just-recipe-graph"',
        svg,
        count=1,
    )


def emit(content: str, output: Path | None) -> None:
    if output is None:
        print(content, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"wrote {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="", help="draw only this recipe and its declared dependencies")
    parser.add_argument("-f", "--format", choices=("svg", "dot"), default="svg")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    try:
        dot_source = render_dot(load_recipes(), root=args.root)
        emit(render_svg(dot_source) if args.format == "svg" else dot_source, args.output)
    except (json.JSONDecodeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
