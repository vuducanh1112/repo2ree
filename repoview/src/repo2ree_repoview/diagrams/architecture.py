from __future__ import annotations

import argparse
import itertools
import tomllib
from collections import Counter
from pathlib import Path

import grimp

from repo2ree_repoview.diagrams import emit
from repo2ree_repoview.graphviz import render
from repo2ree_repoview.repository import ROOT

PYPROJECT = ROOT / "pyproject.toml"

PALETTE = {
    "repo2ree_core": "#3b7dd8",
    "repo2ree_api": "#c2410c",
    "repo2ree_protocol": "#15803d",
    "repo2ree_supervisor": "#7c3aed",
    "repo2ree_cli": "#0891b2",
    "repo2ree_workbench": "#b45309",
}
FALLBACK_COLOR = "#64748b"

LABEL_THRESHOLD = 5


def load_config() -> tuple[list[str], dict[str, int], dict[str, int]]:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]
    roots = list(config["root_packages"])
    ranks: dict[str, int] = {}
    package_ranks: dict[str, int] = {}
    for contract in config.get("contracts", []):
        if contract.get("type") != "layers":
            continue
        containers = contract.get("containers") or []
        for depth, layer in enumerate(contract["layers"]):
            for raw in layer.split(":"):
                module = raw.strip()
                qualified = [f"{c}.{module}" for c in containers] if containers else [module]
                for name in qualified:
                    (package_ranks if name in roots else ranks)[name] = depth
    return roots, ranks, package_ranks


def top_level_owner(module: str, roots: list[str]) -> str | None:
    for root in roots:
        if module == root:
            return None
        if module.startswith(f"{root}."):
            return f"{root}.{module[len(root) + 1 :].split('.')[0]}"
    return None


def build_edges(
    roots: list[str], scope: list[str], *, collapse: bool = False
) -> tuple[list[str], Counter[tuple[str, str]]]:
    graph = grimp.build_graph(*roots)
    edges: Counter[tuple[str, str]] = Counter()
    nodes: set[str] = set()

    def owner(module: str) -> str | None:
        node = top_level_owner(module, scope)
        return None if node is None else (_root_of(node, roots) if collapse else node)

    for module in graph.modules:
        importer = owner(module)
        if importer is None:
            continue
        nodes.add(importer)
        for imported_module in graph.find_modules_directly_imported_by(module):
            imported = owner(imported_module)
            if imported is None or imported == importer:
                continue
            edges[(importer, imported)] += 1
    return sorted(nodes), edges


def find_leaves(nodes: list[str], edges: Counter[tuple[str, str]], ranks: dict[str, int], roots: list[str]) -> set[str]:
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
    package_ranks: dict[str, int] | None = None,
) -> str:
    lines = [
        "digraph architecture {",
        "  rankdir=TB;",
        "  newrank=true;",
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
        by_rank: dict[int, list[str]] = {}
        for node in members:
            if node in ranks:
                by_rank.setdefault(ranks[node], []).append(node)
        tiers = [tier for _, tier in sorted(by_rank.items())]
        for tier in tiers:
            joined = "; ".join(f'"{n}"' for n in tier)
            lines.append(f"    {{ rank=same; {joined}; }}")
        for upper, lower in itertools.pairwise(tiers):
            lines.append(f'    "{upper[0]}" -> "{lower[0]}" [style=invis, weight=10];')
        lines.append("  }")
    if package_ranks:
        drawn = [r for r in roots if any(_root_of(n, roots) == r for n in nodes)]
        tiers_by_rank: dict[int, list[str]] = {}
        for root in drawn:
            if root in package_ranks:
                tiers_by_rank.setdefault(package_ranks[root], []).append(root)
        package_tiers = [tier for _, tier in sorted(tiers_by_rank.items())]

        def anchor(root: str) -> str | None:
            members = sorted(n for n in nodes if _root_of(n, roots) == root)
            return min(members, key=lambda n: (ranks.get(n, len(ranks)), n)) if members else None

        for upper, lower in itertools.pairwise(package_tiers):
            head, tail = anchor(upper[0]), anchor(lower[0])
            if head and tail:
                lines.append(f'  "{head}" -> "{tail}" [style=invis, weight=5];')
    for (importer, imported), weight in sorted(edges.items()):
        color = FALLBACK_COLOR if imported in leaves else PALETTE.get(_root_of(importer, roots), FALLBACK_COLOR)
        width = 1.0 + min(weight, 30) / 12
        label = f'label="{weight}", ' if weight >= LABEL_THRESHOLD else ""
        opacity = "55" if imported in leaves else "99"
        lines.append(f'  "{importer}" -> "{imported}" [{label}penwidth={width:.1f}, color="{color}{opacity}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_dot_collapsed(
    nodes: list[str],
    edges: Counter[tuple[str, str]],
    roots: list[str],
    package_ranks: dict[str, int],
) -> str:
    lines = [
        "digraph workspace {",
        "  rankdir=TB;",
        "  splines=spline;",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13];',
        '  edge [fontname="Helvetica", fontsize=9, color="#94a3b8"];',
    ]
    for node in nodes:
        color = PALETTE.get(node, FALLBACK_COLOR)
        lines.append(f'  "{node}" [label="{node}", fillcolor="{color}22", color="{color}"];')
    by_rank: dict[int, list[str]] = {}
    for node in nodes:
        if node in package_ranks:
            by_rank.setdefault(package_ranks[node], []).append(node)
    tiers = [tier for _, tier in sorted(by_rank.items())]
    for tier in tiers:
        joined = "; ".join(f'"{n}"' for n in tier)
        lines.append(f"  {{ rank=same; {joined}; }}")
    for upper, lower in itertools.pairwise(tiers):
        lines.append(f'  "{upper[0]}" -> "{lower[0]}" [style=invis, weight=10];')
    for (importer, imported), weight in sorted(edges.items()):
        color = PALETTE.get(importer, FALLBACK_COLOR)
        width = 1.0 + min(weight, 90) / 30
        lines.append(f'  "{importer}" -> "{imported}" [label="{weight}", penwidth={width:.1f}, color="{color}99"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_mermaid(nodes: list[str], edges: Counter[tuple[str, str]], roots: list[str]) -> str:
    ids = {node: f"n{index}" for index, node in enumerate(nodes)}
    lines = ["graph TD"]
    grouped: set[str] = set()
    for root in roots:
        members = [n for n in nodes if _root_of(n, roots) == root]
        if not members:
            continue
        lines.append(f'  subgraph {root}["{root}"]')
        lines.extend(f'    {ids[node]}["{_label(node)}"]' for node in members)
        lines.append("  end")
        grouped.update(members)
    lines.extend(f'  {ids[node]}["{node}"]' for node in nodes if node not in grouped)
    for (importer, imported), weight in sorted(edges.items()):
        lines.append(f"  {ids[importer]} -->|{weight}| {ids[imported]}")
    return "\n".join(lines) + "\n"


def main() -> int:
    roots, ranks, package_ranks = load_config()
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", nargs="*", default=None, help="root packages to draw (default: repo2ree_core)")
    parser.add_argument("--all", action="store_true", help="draw every root package in pyproject.toml")
    parser.add_argument(
        "--hide-leaves",
        action="store_true",
        help="omit the leaf primitives every layer may use, leaving just the spine",
    )
    parser.add_argument(
        "--list-packages",
        action="store_true",
        help="print the declared root packages and exit (the Just recipe builds its diagram list from this)",
    )
    parser.add_argument(
        "--collapse",
        action="store_true",
        help="fold each root package to a single node — the workspace in one readable picture (implies --all)",
    )
    parser.add_argument("-f", "--format", choices=("dot", "mermaid", "svg", "png"), default="dot")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout (required for svg/png)")
    args = parser.parse_args()

    if args.list_packages:
        print(" ".join(roots))
        return 0

    scope = roots if (args.all or args.collapse) else (args.packages or ["repo2ree_core"])
    unknown = [p for p in scope if p not in roots]
    if unknown:
        parser.error(f"not a declared root package: {', '.join(unknown)}")

    nodes, edges = build_edges(roots, scope, collapse=args.collapse)
    if args.collapse:
        if args.format == "mermaid":
            text = render_mermaid(nodes, edges, [])
        else:
            text = render_dot_collapsed(nodes, edges, roots, package_ranks)
        return write(text, args, parser)

    leaves = find_leaves(nodes, edges, ranks, roots)
    if args.hide_leaves:
        nodes = [n for n in nodes if n not in leaves]
        edges = Counter({e: w for e, w in edges.items() if e[0] not in leaves and e[1] not in leaves})
        leaves = set()

    if args.format == "mermaid":
        text = render_mermaid(nodes, edges, scope)
    else:
        text = render_dot(nodes, edges, scope, ranks, leaves, package_ranks)

    return write(text, args, parser)


def write(text: str, args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.format in ("svg", "png"):
        if args.output is None:
            parser.error(f"--output is required for {args.format}")
        emit(render(text, args.format), args.output)
    else:
        emit(text, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
