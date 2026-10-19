"""Command line: draw a verified recording, one operation trace page per REE and each sealed REE's provenance.

It reads the verifier's artifact (``verification.json``, written by ``repo2ree_conformance check -o``)
and never verifies again; the recording itself is read only for spans, its context, and commit sizes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_conformance.verification import ARTIFACT, VerifiedModel, read_verification
from repo2ree_recording import read_recording
from repo2ree_traceview.files import commit_sizes, describe, read_spans, repositories, template
from repo2ree_traceview.operations import build_trace, rees
from repo2ree_traceview.provenance import build_provenance, render_text
from repo2ree_traceview.render import render_html
from repo2ree_traceview.spans import SpanIndex


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_traceview", description=__doc__)
    parser.add_argument("verification", type=Path, help="verification.json, or the directory holding it")
    parser.add_argument("--recording", type=Path, help="The recording it verified, if it has moved since")
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
    path = args.verification / ARTIFACT if args.verification.is_dir() else args.verification
    try:
        verification = read_verification(path)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"{path}: not a verification ({exc.__class__.__name__}); run repo2ree_conformance check -o\n")
        return 2
    located = args.recording or (Path(verification.recording) if verification.recording else None)
    if located is None:
        sys.stderr.write(f"{path}: verified no single recording; give --recording\n")
        return 2
    try:
        manifest = read_recording(located)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    model = VerifiedModel.of(verification)
    spans = SpanIndex(read_spans(located, manifest))
    recording = describe(located, manifest)
    sizes = commit_sizes(repositories(located, manifest), args.git_executable)
    chosen = [ree for ree in rees(model) if args.ree is None or ree.startswith(args.ree)]
    if not chosen:
        sys.stderr.write(f"{located}: no REE{f' matching {args.ree}' if args.ree else ''} in this recording\n")
        return 2
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
    page = template()
    for ree in chosen:
        trace = build_trace(model, spans, ree=ree, recording=recording, commit_files=sizes)
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
