"""Command line: collect a deployment's behaviour evidence through its control plane into a recording.

  python -m repo2ree_collect DIR --control-plane URL
      [--archives-in FOLDER]...  REE archives clients downloaded and kept there
      [--ree ID]...              REEs to download now, as their owner would
      [--spans FILE]...          span files the deployment exported
      [--suite NAME] [--test NAME] [--outcome OUTCOME]

Collects the owners' persisted state, then their journals, so the journals reach past the
state's cut. Exits 1 when any source could not be collected; the recording still lists it,
with the problem, so verification reports the gap instead of judging around it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_collect.client import ControlPlane
from repo2ree_collect.collect import collect_control_plane, download_archive, finish, kept_archives, spans, start
from repo2ree_recording import RecordedSource


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo2ree_collect", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="The recording to write (created if absent)")
    parser.add_argument("--control-plane", required=True, help="The API's base URL")
    parser.add_argument("--archives-in", type=Path, action="append", default=[], help="Where clients kept archives")
    parser.add_argument("--ree", action="append", default=[], help="Download this REE's archive (repeatable)")
    parser.add_argument("--spans", type=Path, action="append", default=[], help="A span file to include (repeatable)")
    parser.add_argument("--suite")
    parser.add_argument("--test")
    parser.add_argument("--outcome")
    args = parser.parse_args(argv)

    control_plane = ControlPlane(args.control_plane)
    if not (args.directory / "manifest.json").exists():
        start(args.directory, control_plane=control_plane.url, suite=args.suite, test=args.test)
    collected = kept_archives(args.directory, control_plane, args.archives_in) if args.archives_in else []
    collected += [download_archive(args.directory, control_plane, ree) for ree in args.ree]
    collected += collect_control_plane(args.directory, control_plane)
    collected += spans(args.directory, args.spans, origin="span files the deployment exported")
    finish(args.directory, args.outcome)
    return report(collected)


def report(sources: list[RecordedSource]) -> int:
    for source in sources:
        problem = f": {source.problem}" if source.problem else ""
        sys.stdout.write(f"{source.status:<10} {source.kind:<8} {source.path} <- {source.origin}{problem}\n")
    return 0 if all(source.status == "recorded" for source in sources) else 1
