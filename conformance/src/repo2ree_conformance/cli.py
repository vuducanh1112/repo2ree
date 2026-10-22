"""Command line: generate the published contract, describe or export the spec, validate journals, or check evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_conformance.codegen import render_schema
from repo2ree_conformance.contract import journal_problems
from repo2ree_conformance.export import export_spec
from repo2ree_conformance.files import GENERATED_SCHEMA, SPEC_DIR, load_spec, load_spec_at
from repo2ree_conformance.html import render_html
from repo2ree_conformance.recording import load_recording
from repo2ree_conformance.report import render_json, render_markdown
from repo2ree_conformance.sources import combine, load_evidence
from repo2ree_conformance.verification import ARTIFACT, verify
from repo2ree_conformance.views import diff_specs, render_diff_markdown, system_map


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_conformance", description=__doc__)
    parser.add_argument("--spec", type=Path, default=SPEC_DIR, help="Specification directory")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Write the published event schema from the vocabulary")
    generate.add_argument("--check", action="store_true", help="Fail instead of writing when the schema is stale")
    generate.add_argument("--output", type=Path, default=GENERATED_SCHEMA)

    validate = commands.add_parser(
        "validate-journal", help="Check journal files against the published contract (exit 0/1)"
    )
    validate.add_argument("journals", type=Path, nargs="+", help="Journal files, or directories of them")

    commands.add_parser("describe", help="Validate the specification and print its digest")
    commands.add_parser("map", help="Print the system map (Mermaid) drawn from the specification")
    exported = commands.add_parser("export", help="Write the specification as JSON, for views that compare or draw it")
    exported.add_argument("--at", help="Git revision whose specification to export instead of --spec")
    exported.add_argument("--git-executable", default="git")
    exported.add_argument("--output", "-o", type=Path, help="JSON file to write")
    changes = commands.add_parser("diff", help="Render behavioural changes against the specification at a Git ref")
    changes.add_argument("--base", default="HEAD", help="Git revision holding the previous specification")
    changes.add_argument("--git-executable", default="git")
    changes.add_argument("--output", "-o", type=Path, help="Markdown file to write")

    run = commands.add_parser("check", help="Check evidence against the specification (exit 0/1/2)")
    run.add_argument("--recording", type=Path, action="append", default=[], help="Recording directory (manifest.json)")
    run.add_argument("--journal", type=Path, action="append", default=[], help="Owner journal directory")
    run.add_argument("--git", type=Path, action="append", default=[], help="REE repository root")
    run.add_argument("--stores", type=Path, action="append", default=[], help="Snapshot of persisted owner stores")
    run.add_argument("--git-executable", default="git")
    run.add_argument(
        "--output", "-o", type=Path, help="Directory for the reports and verification.json (read by the views)"
    )

    args = parser.parse_args(argv)
    spec = load_spec(args.spec)
    if args.command == "describe":
        sys.stdout.write(f"{spec.digest}\n  vocabulary {spec.vocabulary_digest}\n")
        for name, entity in sorted(spec.entities.items()):
            edges = sum(len(targets) for targets in entity.edges.values())
            sys.stdout.write(f"  entity {name}: {len(entity.states)} states, {edges} edges, owner {entity.owner}\n")
        for name, boundary in sorted(spec.boundaries.items()):
            sys.stdout.write(f"  boundary {name}: {boundary.sender} -> {boundary.receiver}\n")
        for invariant in spec.invariants:
            sys.stdout.write(f"  invariant {invariant.id} ({invariant.pattern})\n")
        return 0
    if args.command == "export":
        chosen = spec if args.at is None else load_spec_at(args.at, args.git_executable)
        document = json.dumps(export_spec(chosen), indent=2) + "\n"
        if args.output is not None:
            args.output.write_text(document)
        else:
            sys.stdout.write(document)
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
        rendered = render_schema(spec)
        current = args.output.read_text() if args.output.exists() else None
        if args.check:
            if current != rendered:
                sys.stderr.write(f"{args.output} is stale; run `python -m repo2ree_conformance generate`\n")
                return 1
            return 0
        if current != rendered:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered)
        sys.stdout.write(f"{args.output}: {spec.vocabulary_digest}\n")
        return 0
    if args.command == "validate-journal":
        files = [
            found for path in args.journals for found in (sorted(path.glob("*.ndjson")) if path.is_dir() else [path])
        ]
        failed = False
        for path in files:
            problems = journal_problems(spec, path)
            failed = failed or bool(problems)
            sys.stdout.write(f"{'ok' if not problems else 'broken'}: {path}\n")
            sys.stdout.writelines(f"  {problem}\n" for problem in problems)
        if not files:
            sys.stderr.write("no journal files\n")
            return 1
        return 1 if failed else 0
    try:
        recordings = [load_recording(recording, args.git_executable) for recording in args.recording]
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    evidence = combine(*recordings, load_evidence(args.journal, args.git, args.git_executable, args.stores))
    verified = str(args.recording[0].resolve()) if len(args.recording) == 1 else None
    verification = verify(spec, evidence, recording=verified)
    result = verification.result
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "conformance.md").write_text(render_markdown(spec, result))
        (args.output / "conformance.json").write_text(render_json(result))
        (args.output / "conformance.html").write_text(render_html(spec, result))
        # What later steps (the trace views) read instead of verifying again.
        (args.output / ARTIFACT).write_text(verification.model_dump_json())
    summary = ", ".join(f"{rule.rule}={rule.verdict}" for rule in result.rules)
    sys.stdout.write(f"{result.verdict}: {summary}\n")
    return result.exit_code
