"""Trace file, CLI, and Graphviz boundaries."""

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from repo2ree_history.core import trace_journal as journal
from repo2ree_history.shell.outputs import write_files


def graphviz_svg(source: str) -> str:
    return subprocess.run(["dot", "-Tsvg"], input=source, text=True, capture_output=True, check=True).stdout


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("trace_file", type=Path, help="an NDJSON trace file (session or by-test slice)")
    parser.add_argument("--trace", help="trace id, or any unique prefix; omit to list what the file holds")
    parser.add_argument("-f", "--format", choices=("svg", "html", "dot", "graph"), default="svg")
    parser.add_argument("-o", "--out", "--output", type=Path, help="write here instead of stdout")
    parser.add_argument("--shapes", choices=("inline", "none"), default="inline")
    parser.add_argument("--title", help="heading for the graph page; defaults to the root span's name")
    parser.add_argument("--all-spans", action="store_true", help="keep the ASGI http send/receive spans")
    parser.add_argument("--no-links", action="store_true", help="show only the named trace, not what links to it")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="TEXT",
        help="drop spans whose name contains TEXT (or equals it, as =TEXT), re-parenting their children",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="TEXT",
        help="keep only spans whose name contains TEXT, re-parenting across the rest (repeatable)",
    )
    parser.add_argument(
        "--zone",
        action="append",
        default=[],
        metavar="NAME=PATTERN[,PATTERN]",
        help="dot only: box spans whose name matches any PATTERN as component NAME (repeatable)",
    )


def run(args: argparse.Namespace) -> int:
    spans = journal.parse_spans(args.trace_file.read_text(encoding="utf-8"))
    if not spans:
        sys.stderr.write(f"no spans with timestamps in {args.trace_file}" + "\n")
        return 1
    if not args.all_spans:
        spans = [span for span in spans if not span.name.endswith(journal.NOISE_SUFFIXES)]
    # Kept for the diagnostic below: after filtering, a trace that held only
    # spans the filters removed is indistinguishable from one that never
    # existed — and telling a caller to "be more specific" about an id that
    # was right sends them looking in the wrong place.
    traces_before_filtering = {span.trace_id for span in spans}
    spans = journal.prune(spans, args.exclude, args.only)

    by_trace: defaultdict[str, list[journal.Span]] = defaultdict(list)
    for span in spans:
        by_trace[span.trace_id].append(span)

    args.trace_given = bool(args.trace)
    if not args.trace and args.format != "dot":
        for trace_id, members in sorted(by_trace.items(), key=lambda item: -len(item[1])):
            root = min(members, key=lambda span: span.start_ns)
            sys.stdout.write(f"{trace_id}  {len(members):3d} spans  {root.name}" + "\n")
        return 0

    matches = [trace_id for trace_id in by_trace if trace_id.startswith(args.trace or "")]
    if args.trace_given and len(matches) != 1:
        filtered_out = [t for t in traces_before_filtering if t.startswith(args.trace or "")]
        if not matches and filtered_out:
            sys.stderr.write(f"--trace {args.trace!r} has no spans left after --only/--exclude" + "\n")
        else:
            sys.stderr.write(f"--trace {args.trace!r} matched {len(matches)} traces; be more specific" + "\n")
        return 1

    if args.format in ("dot", "graph"):
        # A named trace draws that one operation, link included, with its real
        # values — the question is what flowed. With no trace named it merges
        # the file, where the question is which paths exist at all and values
        # differ per run, so notes fall back to keys.
        if args.trace_given:
            subject = [span for group in journal.collect_groups(dict(by_trace), matches[0]) for span in group.spans]
        else:
            subject = spans
        dot = journal.render_dot(
            subject,
            notes=args.shapes == "inline",
            merged=not args.trace_given,
            zones=journal.parse_zones(args.zone),
        )
        summary = f"{len({journal.node_key(span) for span in subject})} nodes"
        if args.format == "dot":
            return _emit(dot, args.out, summary)
        title = args.title or (subject[0].name if subject else "trace")
        return _emit(journal.render_graph_page(graphviz_svg(dot), title=title), args.out, summary)

    groups = (
        [journal.Group(matches[0], journal.flatten(journal.build_forest(by_trace[matches[0]])), "")]
        if args.no_links
        else journal.collect_groups(dict(by_trace), matches[0])
    )
    scale = journal.build_scale(groups)
    inline = args.shapes == "inline"
    if args.format == "svg":
        out = journal.render_svg(groups, scale, shapes=inline)
    else:
        title = f"{groups[-1].spans[0].anchor} — {args.trace_file.name}"
        out = journal.render_html(groups, scale, shapes=inline, title=title)

    total = sum(len(group.spans) for group in groups)
    return _emit(out, args.out, f"{total} spans, {len(groups)} trace(s)")


def _emit(text: str, out: Path | None, summary: str) -> int:
    if out is None:
        sys.stdout.write(text + "\n")
        return 0
    write_files(out.parent, {out.name: text})
    sys.stderr.write(f"{out}  ({summary})" + "\n")
    return 0
