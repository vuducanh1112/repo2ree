from __future__ import annotations

import fnmatch
from collections import deque
from dataclasses import dataclass

from scripts.vocabulary.discover import contract_sets
from scripts.vocabulary.model import CONTRACTS, Context, Edge, Graph, Located, Relation


@dataclass(frozen=True)
class Report:
    problems: tuple[str, ...]
    names: dict[str, frozenset[str]]
    edges: tuple[tuple[str, ...], ...]
    unanchored: frozenset[str]


def _listed(names: set[str] | frozenset[str]) -> str:
    return ", ".join(sorted(names))


def _sample(names: frozenset[str]) -> str:
    shown = sorted(names)
    return ", ".join(shown[:4]) + (", …" if len(shown) > 4 else "")


def read_all(graph: Graph, context: Context) -> tuple[dict[str, frozenset[str]], list[str]]:
    names: dict[str, frozenset[str]] = {}
    problems: list[str] = []
    for vocabulary in graph.vocabularies:
        found = vocabulary.reader.read(context)
        if not found:
            problems.append(f"{vocabulary.name}: nothing is found at {vocabulary.reader.describe()}")
            continue
        first = found[0]
        problems.extend(
            f"{vocabulary.name}: its copies disagree: {other.where} has "
            f"[{_listed(other.names - first.names)}] and lacks [{_listed(first.names - other.names)}] of {first.where}"
            for other in found[1:]
            if other.names != first.names
        )
        if not first.names:
            problems.append(f"{vocabulary.name}: {first.where} names nothing")
        names[vocabulary.name] = first.names
    return names, problems


def edge_problems(edge: Edge, names: dict[str, frozenset[str]]) -> list[str]:
    if edge.target not in names or any(source not in names for source in edge.sources):
        return []
    if edge.relation is Relation.DERIVED:
        return [f"{edge.target}: a derived edge has no extras"] if edge.extras else []
    target = names[edge.target]
    held = frozenset().union(*(names[source] for source in edge.sources))
    extras = frozenset(edge.extras)
    label = f"{edge.target} {edge.relation} {' | '.join(edge.sources)}"
    problems = [f"{label}: the extra {extra} is no name of {edge.target}" for extra in sorted(extras - target)]
    problems += [f"{label}: the extra {extra} is already in the sources" for extra in sorted(extras & held)]
    if stray := target - held - extras:
        problems.append(f"{label}: [{_listed(stray)}] {'are' if len(stray) > 1 else 'is'} in no source")
    if edge.relation is Relation.EQUALS and (missing := held - target):
        problems.append(f"{label}: lacks [{_listed(missing)}]")
    return problems


def structure_problems(graph: Graph) -> list[str]:
    known = [vocabulary.name for vocabulary in graph.vocabularies]
    problems = [f"{name} is declared twice" for name in sorted({name for name in known if known.count(name) > 1})]
    problems += [f"the root {root} is no vocabulary" for root in graph.roots if root not in known]
    for edge in graph.edges:
        problems += [
            f"an edge names {name}, which is no vocabulary"
            for name in (edge.target, *edge.sources)
            if name not in known
        ]
        if edge.target in edge.sources:
            problems.append(f"{edge.target} is held to itself")
        if edge.target in graph.roots:
            problems.append(
                f"the root {edge.target} is held to {', '.join(edge.sources)}: a root holds, it is not held"
            )
    excepted = {item.site for item in graph.ignored}
    claimed = {site for vocabulary in graph.vocabularies for site in vocabulary.reader.claims()}
    problems += [f"{site} is both an exception and a vocabulary's" for site in sorted(excepted & claimed)]
    return problems


def downstream(graph: Graph, starts: set[str]) -> set[str]:
    reached = set(starts)
    queue = deque(starts)
    while queue:
        current = queue.popleft()
        for edge in graph.edges:
            if current in edge.sources and edge.target not in reached:
                reached.add(edge.target)
                queue.append(edge.target)
    return reached


def anchoring_problems(graph: Graph) -> list[str]:
    anchored = downstream(graph, set(graph.roots))
    return [
        f"{vocabulary.name} reaches no root: hold it to one, or to a vocabulary that does"
        for vocabulary in graph.vocabularies
        if vocabulary.name not in anchored
    ]


def discovered(context: Context) -> dict[str, Located]:
    roots = context.roots()
    found = {
        located.where: located
        for contract in CONTRACTS
        for located in contract_sets(contract, context.contract(contract))
        if located.names & roots
    }
    return found | context.sources()


def claim_problems(graph: Graph, found: dict[str, Located]) -> list[str]:
    patterns = [site for vocabulary in graph.vocabularies for site in vocabulary.reader.claims()]
    patterns += [item.site for item in graph.ignored]
    problems = [
        f"{site} names [{_sample(located.names)}] and no vocabulary or exception claims it"
        for site, located in sorted(found.items())
        if not any(fnmatch.fnmatchcase(site, pattern) for pattern in patterns)
    ]
    problems += [
        f"{entry.site} is claimed but no set is found there: remove the exception"
        for entry in graph.ignored
        if not any(fnmatch.fnmatchcase(site, entry.site) for site in found)
    ]
    return problems


def check(graph: Graph, context: Context) -> Report:
    names, problems = read_all(graph, context)
    problems += structure_problems(graph)
    by_edge = tuple(tuple(edge_problems(edge, names)) for edge in graph.edges)
    problems += [problem for found in by_edge for problem in found]
    unanchored = anchoring_problems(graph)
    problems += unanchored
    problems += claim_problems(graph, discovered(context))
    loose = frozenset(problem.split(" ", 1)[0] for problem in unanchored)
    return Report(problems=tuple(problems), names=names, edges=by_edge, unanchored=loose)


FORMAT = "repo2ree-vocabulary/1"


def export(graph: Graph, report: Report) -> dict[str, object]:
    return {
        "format": FORMAT,
        "roots": list(graph.roots),
        "vocabularies": [
            {
                "name": vocabulary.name,
                "origin": str(vocabulary.origin),
                "summary": vocabulary.summary,
                "where": vocabulary.reader.describe(),
                "names": sorted(report.names.get(vocabulary.name, frozenset())),
                "anchored": vocabulary.name not in report.unanchored,
            }
            for vocabulary in graph.vocabularies
        ],
        "edges": [
            {
                "target": edge.target,
                "relation": str(edge.relation),
                "sources": list(edge.sources),
                "extras": list(edge.extras),
                "problems": list(found),
            }
            for edge, found in zip(graph.edges, report.edges, strict=True)
        ],
        "exceptions": [{"site": item.site, "reason": item.reason} for item in graph.ignored],
        "problems": list(report.problems),
    }


def mermaid(graph: Graph) -> str:
    def node(name: str) -> str:
        return name.replace(".", "_").replace("-", "_")

    lines = ["flowchart TD"]
    for vocabulary in graph.vocabularies:
        shape = (
            f"[[{vocabulary.name}]]"
            if vocabulary.name in graph.roots
            else f"[{vocabulary.name}<br/><i>{vocabulary.origin}</i>]"
        )
        lines.append(f"  {node(vocabulary.name)}{shape}")
    for edge in graph.edges:
        label = str(edge.relation) + (f" +{', '.join(edge.extras)}" if edge.extras else "")
        arrow = "-.->" if edge.relation is Relation.DERIVED else "-->"
        lines += [f"  {node(source)} {arrow}|{label}| {node(edge.target)}" for source in edge.sources]
    return "\n".join(lines)
