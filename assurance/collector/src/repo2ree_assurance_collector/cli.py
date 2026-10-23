"""Command line: collect a deployment's behaviour evidence through its control plane into a dossier.

  python -m repo2ree_assurance_collector DIR [--control-plane URL]
      [--archives-in FOLDER]...  REE archives clients downloaded and kept there
      [--ree ID]...              REEs to download now, as their owner would
      [--skip-owners]            leave the owners' journals and state to a later export
      [--journal-dir DIR [--runs-dir DIR] [--allocations-file FILE]]
                                 the owners' journals and state, exported after they stopped
      [--spans FILE]...          span files the deployment exported
      [--suite NAME] [--test NAME] [--outcome OUTCOME]

Through the control plane, collects the owners' persisted state, then their journals, so the
journals reach past the state's cut. A deployment shutting down for good can instead export
them after its owners stopped (--journal-dir): only then do the journals carry their close.
Collecting into an existing dossier adds to it. Exits 1 when any source could not be
collected; the dossier still lists it, with the problem, so verification reports the gap
instead of judging around it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_assurance_collector.client import ControlPlane
from repo2ree_assurance_collector.collector import (
    collect_control_plane,
    download_archive,
    finish,
    kept_archives,
    record_deployment,
    spans,
    start,
    stopped_owners,
)
from repo2ree_assurance_dossier import DossierSource


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo2ree_assurance_collector", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="The dossier to write (created if absent)")
    parser.add_argument("--control-plane", help="The API's base URL")
    parser.add_argument("--archives-in", type=Path, action="append", default=[], help="Where clients kept archives")
    parser.add_argument("--ree", action="append", default=[], help="Download this REE's archive (repeatable)")
    parser.add_argument("--skip-owners", action="store_true", help="Do not fetch journals and state now")
    parser.add_argument("--journal-dir", type=Path, help="The owners' journal directory, after they stopped")
    parser.add_argument("--runs-dir", type=Path, help="The run store's directory, after its owner stopped")
    parser.add_argument("--allocations-file", type=Path, help="The allocation store, after its owner stopped")
    parser.add_argument("--spans", type=Path, action="append", default=[], help="A span file to include (repeatable)")
    parser.add_argument("--suite")
    parser.add_argument("--test")
    parser.add_argument("--outcome")
    args = parser.parse_args(argv)
    if args.control_plane is None and args.journal_dir is None:
        parser.error("give --control-plane, --journal-dir, or both")
    if args.control_plane is None and (args.archives_in or args.ree):
        parser.error("archives are placed and downloaded through the control plane: give --control-plane")
    if args.journal_dir is None and (args.runs_dir or args.allocations_file):
        parser.error("--runs-dir and --allocations-file export state beside the journals: give --journal-dir")

    control_plane = ControlPlane(args.control_plane) if args.control_plane else None
    if not (args.directory / "manifest.json").exists():
        start(
            args.directory, control_plane=control_plane.url if control_plane else None, suite=args.suite, test=args.test
        )
    collected: list[DossierSource] = []
    if control_plane is not None:
        collected += kept_archives(args.directory, control_plane, args.archives_in) if args.archives_in else []
        collected += [download_archive(args.directory, control_plane, ree) for ree in args.ree]
        if args.skip_owners or args.journal_dir:
            record_deployment(args.directory, control_plane)
        else:
            collected += collect_control_plane(args.directory, control_plane)
    if args.journal_dir is not None:
        collected += stopped_owners(
            args.directory, journals=args.journal_dir, runs=args.runs_dir, allocations=args.allocations_file
        )
    collected += spans(args.directory, args.spans, origin="span files the deployment exported")
    finish(args.directory, args.outcome)
    return report(collected)


def report(sources: list[DossierSource]) -> int:
    for source in sources:
        problem = f": {source.problem}" if source.problem else ""
        sys.stdout.write(f"{source.status:<10} {source.kind:<8} {source.path} <- {source.origin}{problem}\n")
    return 0 if all(source.status == "recorded" for source in sources) else 1
