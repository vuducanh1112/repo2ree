"""Command line: one operation trace page per REE in an e2e recording, and each sealed REE's provenance."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_conformance import check, judge_occurrences, load_evidence, load_spec, recording_inputs, replay
from repo2ree_traceview.files import commit_sizes, read_recording, read_spans, template
from repo2ree_traceview.operations import build_trace, rees
from repo2ree_traceview.provenance import build_provenance, render_text
from repo2ree_traceview.render import render_html
from repo2ree_traceview.spans import SpanIndex


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_traceview", description=__doc__)
    parser.add_argument("recording", type=Path, help="E2E recording directory")
    parser.add_argument("--output", "-o", type=Path, help="Directory for one <ree_id>.html page per REE")
    parser.add_argument("--json", action="store_true", help="Also write <ree_id>.json, the trace model")
    parser.add_argument(
        "--provenance", action="store_true", help="Write <ree_id>.provenance.txt, or print it without --output"
    )
    parser.add_argument("--ree", help="Only the REE whose id starts with this")
    parser.add_argument("--git-executable", default="git")
    args = parser.parse_args(argv)
    if args.output is None and not args.provenance:
        parser.error("nothing to write: give --output, --provenance, or both")
    if args.json and args.output is None:
        parser.error("--json needs --output")
    if not args.recording.is_dir():
        sys.stderr.write(f"{args.recording}: not a recording directory\n")
        return 2

    spec = load_spec()
    journals, repositories, stores = recording_inputs(args.recording)
    evidence = load_evidence(journals, repositories, args.git_executable, stores)
    result = check(spec, evidence)
    model, _, _ = replay(spec, evidence)
    judgements = judge_occurrences(model)
    spans = SpanIndex(read_spans(args.recording))
    recording = read_recording(args.recording)
    sizes = commit_sizes(repositories, args.git_executable)
    chosen = [ree for ree in rees(model) if args.ree is None or ree.startswith(args.ree)]
    if not chosen:
        sys.stderr.write(f"{args.recording}: no REE{f' matching {args.ree}' if args.ree else ''} in this recording\n")
        return 2
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
    page = template()
    for ree in chosen:
        trace = build_trace(model, result, judgements, spans, ree=ree, recording=recording, commit_files=sizes)
        provenance = build_provenance(trace) if args.provenance else None
        text = render_text(provenance) if provenance else f"REE {ree} was not sealed in this recording.\n"
        if args.output is None:
            sys.stdout.write(text)
            continue
        (args.output / f"{ree}.html").write_text(render_html(trace, page))
        if args.json:
            (args.output / f"{ree}.json").write_text(trace.model_dump_json(indent=2))
        if args.provenance:
            (args.output / f"{ree}.provenance.txt").write_text(text)
        reviews = f", {trace.reviews} review attempts not drawn" if trace.reviews else ""
        sys.stdout.write(
            f"{args.output / f'{ree}.html'}: {len(trace.entries)} entries, conformance {trace.verdict}{reviews}\n"
        )
    return 0
