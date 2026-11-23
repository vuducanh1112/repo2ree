from __future__ import annotations

import argparse
import fnmatch
import json
import sys

from scripts.vocabulary.check import check, discovered, downstream, export, mermaid
from scripts.vocabulary.discover import load_contract, source_sites
from scripts.vocabulary.model import Context
from scripts.vocabulary.registry import GRAPH

from repo2ree_assurance_checker.files import load_spec


def context() -> Context:
    return Context(load_contract=load_contract, load_spec=load_spec, discover_sources=source_sites)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.vocabulary")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="hold every vocabulary to its edges and every found set to a claim")
    commands.add_parser("graph", help="print the graph as Mermaid")
    commands.add_parser("export", help="print the graph and what the check found as JSON (repo2ree-vocabulary/1)")
    commands.add_parser("discover", help="list every set of names found, and what claims it")
    impact = commands.add_parser("impact", help="list every vocabulary held, directly or not, to one")
    impact.add_argument("name")
    args = parser.parse_args(argv)

    if args.command == "export":
        print(json.dumps(export(GRAPH, check(GRAPH, context())), indent=2))
        return 0
    if args.command == "graph":
        print(mermaid(GRAPH))
        return 0
    if args.command == "impact":
        if args.name not in {vocabulary.name for vocabulary in GRAPH.vocabularies}:
            parser.error(f"{args.name} is no vocabulary of the graph")
        for name in sorted(downstream(GRAPH, {args.name}) - {args.name}):
            print(f"{name}\t{GRAPH.vocabulary(name).reader.describe()}")
        return 0
    if args.command == "discover":
        claims = [(site, vocabulary.name) for vocabulary in GRAPH.vocabularies for site in vocabulary.reader.claims()]
        claims += [(item.site, "exception") for item in GRAPH.ignored]
        for site, located in sorted(discovered(context()).items()):
            by = next((name for pattern, name in claims if fnmatch.fnmatchcase(site, pattern)), "UNCLAIMED")
            print(f"{by}\t{site}\t{', '.join(sorted(located.names))}")
        return 0

    report = check(GRAPH, context())
    for problem in report.problems:
        print(f"problem  {problem}", file=sys.stderr)
    if report.problems:
        print(f">> {len(report.problems)} vocabulary problems", file=sys.stderr)
        return 1
    print(f">> vocabulary graph holds: {len(GRAPH.vocabularies)} vocabularies, {len(GRAPH.edges)} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
