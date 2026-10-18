"""Command line: generate the runtime machines, describe the spec, or check evidence."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_conformance.check import check, replay
from repo2ree_conformance.codegen import render_machines
from repo2ree_conformance.files import GENERATED_MACHINES, SPEC_DIR, load_spec, load_spec_at
from repo2ree_conformance.html import render_html
from repo2ree_conformance.report import render_json, render_markdown
from repo2ree_conformance.sources import load_evidence, recording_inputs
from repo2ree_conformance.views import diff_specs, render_diff_markdown, system_map


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_conformance", description=__doc__)
    parser.add_argument("--spec", type=Path, default=SPEC_DIR, help="Specification directory")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Write the runtime machines module from the specification")
    generate.add_argument("--check", action="store_true", help="Fail instead of writing when the module is stale")
    generate.add_argument("--output", type=Path, default=GENERATED_MACHINES)

    commands.add_parser("describe", help="Validate the specification and print its digest")
    commands.add_parser("map", help="Print the system map (Mermaid) drawn from the specification")
    changes = commands.add_parser("diff", help="Render behavioural changes against the specification at a Git ref")
    changes.add_argument("--base", default="HEAD", help="Git revision holding the previous specification")
    changes.add_argument("--git-executable", default="git")
    changes.add_argument("--output", "-o", type=Path, help="Markdown file to write")

    run = commands.add_parser("check", help="Check evidence against the specification (exit 0/1/2)")
    run.add_argument("--recording", type=Path, action="append", default=[], help="E2E recording directory")
    run.add_argument("--journal", type=Path, action="append", default=[], help="Owner journal directory")
    run.add_argument("--git", type=Path, action="append", default=[], help="REE repository root")
    run.add_argument("--stores", type=Path, action="append", default=[], help="Snapshot of persisted owner stores")
    run.add_argument("--git-executable", default="git")
    run.add_argument("--output", "-o", type=Path, help="Directory for conformance.md and conformance.json")

    args = parser.parse_args(argv)
    spec = load_spec(args.spec)
    if args.command == "describe":
        sys.stdout.write(f"{spec.digest}\n")
        for name, entity in sorted(spec.entities.items()):
            edges = sum(len(targets) for targets in entity.edges.values())
            sys.stdout.write(f"  entity {name}: {len(entity.states)} states, {edges} edges, owner {entity.owner}\n")
        for name, boundary in sorted(spec.boundaries.items()):
            sys.stdout.write(f"  boundary {name}: {boundary.sender} -> {boundary.receiver}\n")
        for invariant in spec.invariants:
            sys.stdout.write(f"  invariant {invariant.id} ({invariant.pattern})\n")
        return 0
    if args.command == "map":
        sys.stdout.write(system_map(spec) + "\n")
        return 0
    if args.command == "diff":
        base = load_spec_at(args.base, args.git_executable)
        rendered = render_diff_markdown(diff_specs(base, spec), base.digest, spec.digest)
        if args.output is not None:
            args.output.write_text(rendered)
        else:
            sys.stdout.write(rendered)
        return 0
    if args.command == "generate":
        rendered = render_machines(spec)
        current = args.output.read_text() if args.output.exists() else None
        if args.check:
            if current != rendered:
                sys.stderr.write(f"{args.output} is stale; run `python -m repo2ree_conformance generate`\n")
                return 1
            return 0
        if current != rendered:
            args.output.write_text(rendered)
        sys.stdout.write(f"{args.output}: {spec.digest}\n")
        return 0
    journals, repositories, stores = list(args.journal), list(args.git), list(args.stores)
    for recording in args.recording:
        found_journals, found_repositories, found_stores = recording_inputs(recording)
        journals.extend(found_journals)
        repositories.extend(found_repositories)
        stores.extend(found_stores)
    evidence = load_evidence(journals, repositories, args.git_executable, stores)
    result = check(spec, evidence)
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "conformance.md").write_text(render_markdown(spec, result))
        (args.output / "conformance.json").write_text(render_json(result))
        (args.output / "conformance.html").write_text(render_html(spec, result, replay(spec, evidence)[0]))
    summary = ", ".join(f"{rule.rule}={rule.verdict}" for rule in result.rules)
    sys.stdout.write(f"{result.verdict}: {summary}\n")
    return result.exit_code
