"""File and command-line boundary for REE views."""

import argparse
import sys
from pathlib import Path

from repo2ree_history.core.ree_filmstrip import (
    build_rows,
    diff_frames,
    parse_frames,
    render_browser,
    render_svg,
    render_timeline,
)
from repo2ree_history.shell.outputs import write_files


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-f", "--format", choices=("matrix", "timeline", "browse"), default="matrix")
    parser.add_argument("--frames", type=Path, required=True, help="capture to render")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")


def run(args: argparse.Namespace) -> int:
    frames = parse_frames(args.frames.read_text(encoding="utf-8"))
    if not frames:
        raise ValueError("capture holds no frames")
    if args.format == "matrix":
        rendered = render_svg(frames, build_rows(frames))
    elif args.format == "timeline":
        rendered = render_timeline(frames, diff_frames(frames))
    else:
        rendered = render_browser(frames[-1])
    if args.output is None:
        sys.stdout.write(rendered + "\n")
    else:
        write_files(args.output.parent, {args.output.name: rendered + "\n"})
        sys.stdout.write(f"wrote {args.output}" + "\n")
    return 0
