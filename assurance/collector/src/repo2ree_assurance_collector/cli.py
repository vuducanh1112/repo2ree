from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repo2ree_assurance_collector.client import SAFE_NAME, ControlPlane
from repo2ree_assurance_collector.collector import (
    collect_control_plane,
    download_archive,
    environment_journals,
    finish,
    kept_archives,
    kept_rees,
    record_deployment,
    spans,
    start,
    stopped_owners,
    stopped_stores,
)
from repo2ree_assurance_dossier import DossierSource


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo2ree_assurance_collector", formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", type=Path, help="The dossier to write (created if absent)")
    parser.add_argument("--control-plane", help="The API's base URL")
    parser.add_argument("--archives-in", type=Path, action="append", default=[], help="Where clients kept archives")
    parser.add_argument("--ree", action="append", default=[], help="Download this REE's archive (repeatable)")
    parser.add_argument(
        "--kept-rees", type=Path, help="REEs a client ran ree in itself: one folder each, with the histories it kept"
    )
    parser.add_argument(
        "--environment-journal-dir", type=Path, help="The journals a client kept as the REEs' environment"
    )
    parser.add_argument("--skip-owners", action="store_true", help="Do not fetch journals and state now")
    parser.add_argument("--journal-dir", type=Path, help="The owners' journal directory, after they stopped")
    parser.add_argument("--runs-dir", type=Path, help="The run store's directory, after its owner stopped")
    parser.add_argument(
        "--store-journal-dir",
        action="append",
        default=[],
        metavar="STORE=DIR",
        help="A store's journal directory, after its workbench stopped (repeatable)",
    )
    parser.add_argument("--spans", type=Path, action="append", default=[], help="A span file to include (repeatable)")
    parser.add_argument("--suite")
    parser.add_argument("--test")
    parser.add_argument("--outcome")
    args = parser.parse_args(argv)
    stores: dict[str, Path] = {}
    for given in args.store_journal_dir:
        store_id, separator, folder = given.partition("=")
        if not separator or not SAFE_NAME.match(store_id) or not folder:
            parser.error(f"--store-journal-dir takes STORE=DIR, not {given!r}")
        stores[store_id] = Path(folder)
    if args.control_plane is None and args.journal_dir is None and args.kept_rees is None:
        parser.error("give --control-plane, --journal-dir, or --kept-rees")
    if stores and args.journal_dir is None:
        parser.error("--store-journal-dir exports journals beside the control plane's: give --journal-dir")
    if args.control_plane is None and (args.archives_in or args.ree):
        parser.error("archives are placed and downloaded through the control plane: give --control-plane")
    if args.journal_dir is None and args.runs_dir:
        parser.error("--runs-dir exports state beside the journals: give --journal-dir")

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
    collected += kept_rees(args.directory, args.kept_rees) if args.kept_rees else []
    if args.environment_journal_dir is not None:
        collected += environment_journals(args.directory, args.environment_journal_dir)
    if args.journal_dir is not None:
        collected += stopped_owners(args.directory, journals=args.journal_dir, runs=args.runs_dir)
        collected += stopped_stores(args.directory, stores)
    collected += spans(args.directory, args.spans, origin="span files the deployment exported")
    finish(args.directory, args.outcome)
    return report(collected)


def report(sources: list[DossierSource]) -> int:
    for source in sources:
        problem = f": {source.problem}" if source.problem else ""
        sys.stdout.write(f"{source.status:<10} {source.kind:<8} {source.path} <- {source.origin}{problem}\n")
    return 0 if all(source.status == "recorded" for source in sources) else 1
