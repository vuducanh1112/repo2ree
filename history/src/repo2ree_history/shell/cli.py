"""Command-line boundary for evidence collection and presentation."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from subprocess import SubprocessError

from repo2ree_history.core.models import SystemExecution
from repo2ree_history.core.sequence import render_sequence
from repo2ree_history.core.sequence_svg import render_svg as render_sequence_svg
from repo2ree_history.shell import ree_filmstrip, trace_journal
from repo2ree_history.shell.execution import load_execution
from repo2ree_history.shell.outputs import write_files, write_outputs
from repo2ree_history.shell.recording import assemble_recording


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("assemble", "Assemble a preserved recording"),
        ("sequence", "Render an execution as Mermaid"),
        ("sequence-svg", "Render an execution as SVG"),
    ):
        sub = commands.add_parser(command, help=help_text)
        if command == "assemble":
            sub.add_argument("--strict", action="store_true", help="Write evidence, then fail on invalid records")
        sub.add_argument("input", type=Path)
        sub.add_argument("--output", "-o", type=Path, required=True)
    schema = commands.add_parser("schema", help="Export the execution JSON schema")
    schema.add_argument("--output", "-o", type=Path)
    ree_filmstrip.configure(commands.add_parser("ree-filmstrip", help="Render captured REE states"))
    trace_journal.configure(commands.add_parser("trace-journal", help="Render captured spans"))
    args = parser.parse_args(argv)
    try:
        if args.command == "ree-filmstrip":
            return ree_filmstrip.run(args)
        if args.command == "trace-journal":
            return trace_journal.run(args)
        if args.command == "assemble":
            result = assemble_recording(args.input)
            write_outputs(result, args.output)
            if args.strict and any(issue.severity == "invalid" for issue in result.diagnostics):
                return 1
            sys.stdout.write(
                f"{len(result.executions)} executions; {len(result.unassigned)} unassigned; output: {args.output}\n"
            )
        else:
            if args.command == "schema":
                text = json.dumps(SystemExecution.model_json_schema(), indent=2) + "\n"
            else:
                execution = load_execution(args.input)
                text = render_sequence_svg(execution) if args.command == "sequence-svg" else render_sequence(execution)
                if args.command == "sequence" and args.output.suffix == ".md":
                    text = "```mermaid\n" + text + "```\n"
            if args.output is None:
                sys.stdout.write(text)
            else:
                write_files(args.output.parent, {args.output.name: text})
    except (OSError, ValueError, SubprocessError) as exc:
        sys.stderr.write(f"history: {exc}\n")
        return 1
    return 0
