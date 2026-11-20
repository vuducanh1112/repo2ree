"""Render the declared Just recipe dependency graph.

Edges follow execution order: prerequisites point to the recipe that consumes
them, while subsequent dependencies point away from the recipe whose body runs
first. Recipes with no incoming execution edge share the first rank.

What a recipe runs, a test suite or the exercise cases, it declares as data:
``[metadata("runs", "<path>")]``, each path from the repository root. The graph
draws each path as a node of its own, with an edge from every recipe that runs
it. ``undeclared_runs`` holds the declarations to the recipes: every suite a
recipe names (a ``testbed/suites/`` path, a Playwright project, a showcase
command) is declared, and every declared path exists.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterator
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
    arguments: tuple[JsonValue, ...] = ()


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
    # The arguments written as literals.
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recipe:
    name: str
    group: str
    private: bool
    has_body: bool
    dependencies: tuple[Dependency, ...]
    doc: str = ""
    parameters: tuple[str, ...] = ()
    # What it declares it runs: test suites and the exercise cases, each a path from the repository root.
    runs: tuple[str, ...] = ()
    # The literal text of its body.
    text: str = ""

    @property
    def aggregate(self) -> bool:
        return bool(self.dependencies) and not self.has_body


def parse_recipes(document: dict[str, Any]) -> dict[str, Recipe]:
    """Convert Just's JSON dump into the small model the diagram and the overview draw."""
    return _recipes(_Dump.model_validate(document))


def _strings(value: JsonValue) -> Iterator[str]:
    """The literal strings of a fragment of Just's dump, in order."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _runs(attributes: tuple[JsonValue, ...]) -> tuple[str, ...]:
    """The paths of a recipe's ``[metadata("runs", ...)]`` attributes."""
    paths: list[str] = []
    for attribute in attributes:
        values = attribute.get("metadata") if isinstance(attribute, dict) else None
        if isinstance(values, list) and values and values[0] == "runs":
            paths += [str(value).rstrip("/") for value in values[1:]]
    return tuple(paths)


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
                Dependency(
                    dependency.recipe,
                    subsequent=index >= priors,
                    arguments=tuple(argument for argument in dependency.arguments if isinstance(argument, str)),
                )
                for index, dependency in enumerate(raw.dependencies)
            ),
            doc=raw.doc or "",
            parameters=tuple(parameter.name for parameter in raw.parameters),
            runs=_runs(raw.attributes),
            text=" ".join(_strings(list(raw.body))),
        )
    return parsed


def read_recipes(dump: str) -> dict[str, Recipe]:
    """The recipes of Just's JSON dump (``just --dump --dump-format json``)."""
    return _recipes(_Dump.model_validate_json(dump))


def load_recipes() -> dict[str, Recipe]:
    dump = subprocess.run(
        ["just", "--dump", "--dump-format", "json"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    return read_recipes(dump)


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


# What runs a suite without naming its path: the command, and the suite it runs.
SUITE_COMMANDS = {
    "repo2ree_testbed api-showcase run": "testbed/suites/showcase",
    "repo2ree_testbed cli-showcase run": "testbed/suites/showcase",
}
# The recipe that runs the Playwright project its first argument names.
PLAYWRIGHT_RECIPE = "_source-stack-playwright"
PLAYWRIGHT_CONFIG = "gui/playwright.config.ts"


def playwright_projects(config: str) -> dict[str, str]:
    """Each Playwright project of ``config``'s text, and the directory it runs, from the repository root."""
    pairs = re.findall(r'name:\s*"([^"]+)",\s*testDir:\s*"\./([^"]+)"', config)
    return {name: f"gui/{directory.rstrip('/')}" for name, directory in pairs}


def _named_suites(recipe: Recipe, projects: dict[str, str]) -> set[str]:
    """The suites ``recipe`` names: by path, by Playwright project, or by a command that runs one."""
    named = {match.rstrip("/.") for match in re.findall(r"testbed/suites/[\w./-]+", recipe.text)}
    names = set(re.findall(r"--project[= ]([\w-]+)", recipe.text))
    names |= {
        dependency.arguments[0]
        for dependency in recipe.dependencies
        if dependency.recipe == PLAYWRIGHT_RECIPE and dependency.arguments
    }
    named |= {projects.get(name, f"an unknown Playwright project {name}") for name in names}
    named |= {suite for command, suite in SUITE_COMMANDS.items() if command in recipe.text}
    return named


def _suite_of(path: str) -> str:
    """The suite a path in one names: ``testbed/suites/<suite>``, or the path itself."""
    parts = path.split("/")
    return "/".join(parts[:3]) if parts[:2] == ["testbed", "suites"] else path


def undeclared_runs(recipes: dict[str, Recipe], root: Path = ROOT) -> list[str]:
    """How the recipes' ``runs`` declarations fall short: a suite a recipe names that it does not declare, or a
    declared path that is not there."""
    projects = playwright_projects((root / PLAYWRIGHT_CONFIG).read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, recipe in sorted(recipes.items()):
        problems += [
            f'{name} runs {named} and does not declare it: [metadata("runs", "{_suite_of(named)}")]'
            for named in sorted(_named_suites(recipe, projects))
            if not any(named == path or named.startswith(f"{path}/") for path in recipe.runs)
        ]
        problems += [
            f"{name} declares it runs {path}, which is not there" for path in recipe.runs if not (root / path).exists()
        ]
    return problems


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
    lines.extend(
        f'  {quote("runs:" + path)} [label={quote(path)}, shape=folder, style=filled, fillcolor="#f8fafc", '
        f'color="#0f766e", fontcolor="#0f766e", tooltip="what the recipes run"];'
        for path in sorted({path for recipe in visible.values() for path in recipe.runs})
    )
    if sources:
        joined = "; ".join(quote(name) for name in sources)
        lines.extend(["", f"  {{ rank=source; {joined}; }}"])
    if edges:
        lines.append("")
    for tail, head, subsequent in sorted(edges):
        edge_attributes = ' [style=dashed, label="after", color="#a78bfa"]' if subsequent else ""
        lines.append(f"  {quote(tail)} -> {quote(head)}{edge_attributes};")
    lines.extend(
        f'  {quote(name)} -> {quote("runs:" + path)} [style=dotted, color="#0f766e", label="runs"];'
        for name, recipe in sorted(visible.items())
        for path in recipe.runs
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="", help="draw only this recipe and its declared dependencies")
    parser.add_argument("--dump", type=Path, help="Just's JSON dump to draw (default: dump the justfile now)")
    parser.add_argument("-f", "--format", choices=("svg", "dot"), default="svg")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    try:
        recipes = read_recipes(args.dump.read_text(encoding="utf-8")) if args.dump else load_recipes()
        dot_source = render_dot(recipes, root=args.root)
        emit(inline_svg(dot_source, css_class="just-recipe-graph") if args.format == "svg" else dot_source, args.output)
    except (OSError, ValueError, ValidationError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
