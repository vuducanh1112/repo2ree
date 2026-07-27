"""Render the backend import graph the architecture contracts are checked against.

``lint-imports`` answers "is the graph legal?" and prints nothing when it is.
This answers "what does the graph look like?" — the picture dependency-cruiser
draws for the frontend, for the same reason: a contract tells you a rule held,
a diagram tells you whether the shape it describes is the one you meant.

Both read the same source. import-linter is built on grimp, and this builds the
grimp graph over exactly the ``root_packages`` declared in pyproject.toml, so
the diagram cannot drift from the contracts by construction. Nodes are the
top-level children of each root package (``repo2ree_core.evidence``, not every
module beneath it); an edge means at least one module under the tail imports at
least one module under the head, labelled with how many such imports there are.

Where a layers contract covers a package, its nodes are ranked in the declared
order, so a legal graph reads strictly downward and a violation would be the one
edge pointing back up the page.

    python scripts/arch_graph.py                       # core, as DOT
    python scripts/arch_graph.py --all -f svg -o g.svg # everything, rendered
    python scripts/arch_graph.py -f mermaid            # to paste into docs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

import grimp

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# One hue per root package, so a cross-package edge is visible as a colour
# change rather than something you have to trace to the cluster border.
PALETTE = {
    "repo2ree_core": "#3b7dd8",
    "repo2ree_api": "#c2410c",
    "repo2ree_protocol": "#15803d",
    "repo2ree_supervisor": "#7c3aed",
    "repo2ree_executor": "#0891b2",
    "repo2ree_agent": "#b45309",
}
FALLBACK_COLOR = "#64748b"

# Below this many underlying imports, an edge carries its weight in thickness
# alone — see the comment where edges are emitted.
LABEL_THRESHOLD = 5


def load_config() -> tuple[list[str], dict[str, int]]:
    """Root packages and each module's rank within its layers contract.

    Rank is what lets the drawing assert the same thing the contract does: a
    lower number sits higher on the page, matching ``layers`` order (first entry
    is the top tier). Modules outside any layers contract get no rank and float.
    """
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]
    ranks: dict[str, int] = {}
    for contract in config.get("contracts", []):
        if contract.get("type") != "layers":
            continue
        for depth, layer in enumerate(contract["layers"]):
            # A layer may hold independent siblings, written "a : b".
            for module in layer.split(":"):
                ranks[module.strip()] = depth
    return list(config["root_packages"]), ranks


def top_level_owner(module: str, roots: list[str]) -> str | None:
    """The diagram node a module belongs to, or None if it is outside scope.

    A root package's own ``__init__`` owns nothing below it, so it maps to no
    node: drawing ``repo2ree_core`` beside ``repo2ree_core.ree`` would put a
    container and one of its contents on the same footing.
    """
    for root in roots:
        if module == root:
            return None
        if module.startswith(f"{root}."):
            return f"{root}.{module[len(root) + 1 :].split('.')[0]}"
    return None


def build_edges(roots: list[str], scope: list[str]) -> tuple[list[str], Counter[tuple[str, str]]]:
    """Aggregate the module graph up to one node per top-level package.

    Counting is deliberate: an edge carrying thirty imports and an edge carrying
    one look identical in a plain arrow, and they are not the same fact about
    how entangled two packages are.
    """
    graph = grimp.build_graph(*roots)
    edges: Counter[tuple[str, str]] = Counter()
    nodes: set[str] = set()
    for module in graph.modules:
        importer = top_level_owner(module, scope)
        if importer is None:
            continue
        nodes.add(importer)
        for imported_module in graph.find_modules_directly_imported_by(module):
            imported = top_level_owner(imported_module, scope)
            if imported is None or imported == importer:
                continue
            edges[(importer, imported)] += 1
    return sorted(nodes), edges


def find_leaves(nodes: list[str], edges: Counter[tuple[str, str]], ranks: dict[str, int], roots: list[str]) -> set[str]:
    """The nodes that sit under everything: outside any layer, depending only on
    each other.

    Derived rather than listed, so the drawing cannot disagree with the code
    about what a leaf is. Nodes named in a layers contract are excluded by
    construction — ``domain`` depends on nothing but leaves, and calling it one
    would erase the distinction between "the vocabulary" and "the utilities".

    Only packages that *declare* a spine are searched. In one that does not,
    every module is a sink relative to its siblings, and the rule would happily
    conclude that all of ``repo2ree_protocol`` is a leaf primitive — hiding the
    package rather than simplifying it.
    """
    layered = {r for r in roots if any(m == r or m.startswith(f"{r}.") for m in ranks)}
    leaves = {n for n in nodes if n not in ranks and _root_of(n, roots) in layered}
    while True:
        shrunk = {
            leaf for leaf in leaves if all(imported in leaves for (importer, imported) in edges if importer == leaf)
        }
        if shrunk == leaves:
            return leaves
        leaves = shrunk


def _label(node: str) -> str:
    return node.split(".", 1)[1] if "." in node else node


def _root_of(node: str, roots: list[str]) -> str:
    return next((r for r in roots if node == r or node.startswith(f"{r}.")), node)


def render_dot(
    nodes: list[str],
    edges: Counter[tuple[str, str]],
    roots: list[str],
    ranks: dict[str, int],
    leaves: set[str],
) -> str:
    lines = [
        "digraph architecture {",
        "  rankdir=TB;",
        "  splines=spline;",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=8, color="#94a3b8"];',
    ]
    for root in roots:
        members = [n for n in nodes if _root_of(n, roots) == root]
        if not members:
            continue
        color = PALETTE.get(root, FALLBACK_COLOR)
        lines += [
            f"  subgraph cluster_{root} {{",
            f'    label="{root}"; fontname="Helvetica"; fontsize=13; color="{color}"; style=rounded;',
        ]
        for node in members:
            style = (
                f'style="rounded,filled,dashed", fillcolor="#f8fafc", color="{FALLBACK_COLOR}", fontcolor="#475569"'
                if node in leaves
                else f'fillcolor="{color}22", color="{color}"'
            )
            lines.append(f'    "{node}" [label="{_label(node)}", {style}];')
        leaf_members = [n for n in members if n in leaves]
        if leaf_members:
            joined = "; ".join(f'"{n}"' for n in leaf_members)
            lines.append(f"    {{ rank=sink; {joined}; }}")
        # Pin ranked nodes into their contract tier so a legal graph flows down.
        by_rank: dict[int, list[str]] = {}
        for node in members:
            if node in ranks:
                by_rank.setdefault(ranks[node], []).append(node)
        tiers = [tier for _, tier in sorted(by_rank.items())]
        for tier in tiers:
            joined = "; ".join(f'"{n}"' for n in tier)
            lines.append(f"    {{ rank=same; {joined}; }}")
        # Hold the tiers in contract order even where no real import chains
        # them, so the declared layering is what the vertical axis means.
        for upper, lower in zip(tiers, tiers[1:], strict=False):
            lines.append(f'    "{upper[0]}" -> "{lower[0]}" [style=invis, weight=10];')
        lines.append("  }")
    for (importer, imported), weight in sorted(edges.items()):
        color = FALLBACK_COLOR if imported in leaves else PALETTE.get(_root_of(importer, roots), FALLBACK_COLOR)
        width = 1.0 + min(weight, 30) / 12
        # Thin edges are already legible as thin; a label on every one of them
        # buries the handful of couplings heavy enough to be worth arguing about.
        label = f'label="{weight}", ' if weight >= LABEL_THRESHOLD else ""
        opacity = "55" if imported in leaves else "99"
        lines.append(f'  "{importer}" -> "{imported}" [{label}penwidth={width:.1f}, color="{color}{opacity}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_mermaid(nodes: list[str], edges: Counter[tuple[str, str]], roots: list[str]) -> str:
    """Mermaid for embedding in Markdown, which GitHub renders inline."""
    ids = {node: f"n{index}" for index, node in enumerate(nodes)}
    lines = ["graph TD"]
    for root in roots:
        members = [n for n in nodes if _root_of(n, roots) == root]
        if not members:
            continue
        lines.append(f'  subgraph {root}["{root}"]')
        for node in members:
            lines.append(f'    {ids[node]}["{_label(node)}"]')
        lines.append("  end")
    for (importer, imported), weight in sorted(edges.items()):
        lines.append(f"  {ids[importer]} -->|{weight}| {ids[imported]}")
    return "\n".join(lines) + "\n"


def main() -> int:
    roots, ranks = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", nargs="*", default=None, help="root packages to draw (default: repo2ree_core)")
    parser.add_argument("--all", action="store_true", help="draw every root package in pyproject.toml")
    parser.add_argument(
        "--hide-leaves",
        action="store_true",
        help="omit the leaf primitives every layer may use, leaving just the spine",
    )
    parser.add_argument("-f", "--format", choices=("dot", "mermaid", "svg", "png"), default="dot")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout (required for svg/png)")
    args = parser.parse_args()

    scope = roots if args.all else (args.packages or ["repo2ree_core"])
    unknown = [p for p in scope if p not in roots]
    if unknown:
        parser.error(f"not a declared root package: {', '.join(unknown)}")

    # The graph is always built over every root package: an edge out of the
    # drawn scope still has to be seen to be excluded deliberately.
    nodes, edges = build_edges(roots, scope)
    leaves = find_leaves(nodes, edges, ranks, roots)
    if args.hide_leaves:
        nodes = [n for n in nodes if n not in leaves]
        edges = Counter({e: w for e, w in edges.items() if e[0] not in leaves and e[1] not in leaves})
        leaves = set()

    if args.format == "mermaid":
        text = render_mermaid(nodes, edges, scope)
    else:
        text = render_dot(nodes, edges, scope, ranks, leaves)

    if args.format in ("svg", "png"):
        if args.output is None:
            parser.error(f"--output is required for {args.format}")
        args.output.write_bytes(
            subprocess.run(["dot", f"-T{args.format}"], input=text.encode(), capture_output=True, check=True).stdout
        )
        print(f"wrote {args.output}", file=sys.stderr)
        return 0

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
