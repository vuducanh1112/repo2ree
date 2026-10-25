"""Command line: ``trace`` draws one verified dossier per REE; ``operations`` folds many into one catalogue.

Both read ``verification.json`` (from ``repo2ree_assurance_checker check -o``) and never verify again.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from repo2ree_assurance_checker.verification import ARTIFACT, Verification, VerifiedModel, read_verification
from repo2ree_assurance_dossier import Dossier, read_dossier
from repo2ree_assurance_traceview.catalogue import Undrawn, build_catalogue
from repo2ree_assurance_traceview.files import commit_sizes, describe, read_spans, repositories, template
from repo2ree_assurance_traceview.model import BehaviourTrace
from repo2ree_assurance_traceview.operations import build_trace, rees
from repo2ree_assurance_traceview.provenance import build_provenance, render_text
from repo2ree_assurance_traceview.render import render_html


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo2ree_assurance_traceview", description=__doc__)
    parser.add_argument("--git-executable", default="git")
    commands = parser.add_subparsers(dest="command", required=True)

    trace = commands.add_parser("trace", help="Draw one dossier: a behaviour trace page per REE, and provenance")
    trace.add_argument("verification", type=Path, help="verification.json, or the directory holding it")
    trace.add_argument("--dossier", type=Path, help="The dossier it verified, if it has moved since")
    trace.add_argument("--output", "-o", type=Path, help="Directory for one <ree_id>.html page per REE")
    trace.add_argument("--json", action="store_true", help="Also write <ree_id>.json, the trace model")
    trace.add_argument(
        "--provenance", action="store_true", help="Write <ree_id>.provenance.txt, or print it without --output"
    )
    trace.add_argument("--ree", help="Only the REE whose id starts with this")

    operations = commands.add_parser(
        "operations", help="Fold many dossiers' traces into one catalogue of operations (JSON)"
    )
    operations.add_argument(
        "verifications", type=Path, nargs="*", help="verification.json files, or the directories holding them"
    )
    operations.add_argument("--output", "-o", type=Path, help="Write the catalogue here instead of printing it")
    return parser


class _UnreadableError(ValueError):
    """A verification, or the dossier it names, that cannot be read."""


@dataclass(frozen=True)
class _Verified:
    verification: Verification
    located: Path
    dossier: Dossier

    @classmethod
    def read(cls, given: Path, dossier: Path | None = None) -> _Verified:
        path = given / ARTIFACT if given.is_dir() else given
        try:
            verification = read_verification(path)
        except (OSError, ValueError) as exc:
            raise _UnreadableError(
                f"{path}: not a verification ({exc.__class__.__name__}); run repo2ree_assurance_checker check -o"
            ) from exc
        located = dossier or (Path(verification.dossier) if verification.dossier else None)
        if located is None:
            raise _UnreadableError(f"{path}: verified no single dossier; give --dossier")
        try:
            return cls(verification, located, read_dossier(located))
        except ValueError as exc:
            raise _UnreadableError(str(exc)) from exc

    def traces(self, git: str, ree: str | None = None, *, count_files: bool = True) -> list[BehaviourTrace]:
        model = VerifiedModel.of(self.verification)
        spans = read_spans(self.located, self.dossier)
        info = describe(self.located, self.dossier)
        files = commit_sizes(repositories(self.located, self.dossier), git) if count_files else {}
        chosen = [one for one in rees(model) if ree is None or one.startswith(ree)]
        return [build_trace(model, spans, ree=one, dossier=info, commit_files=files) for one in chosen]


def trace(args: argparse.Namespace) -> int:
    if args.output is None and not args.provenance:
        sys.stderr.write("nothing to write: give --output, --provenance, or both\n")
        return 2
    if args.json and args.output is None:
        sys.stderr.write("--json needs --output\n")
        return 2
    try:
        verified = _Verified.read(args.verification, args.dossier)
    except _UnreadableError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    traces = verified.traces(args.git_executable, args.ree)
    if not traces:
        sys.stderr.write(f"{verified.located}: no REE{f' matching {args.ree}' if args.ree else ''} in this dossier\n")
        return 2
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
    page = template()
    for one in traces:
        provenance = build_provenance(one) if args.provenance else None
        text = render_text(provenance) if provenance else f"REE {one.ree} was not sealed in this dossier.\n"
        if args.output is None:
            sys.stdout.write(text)
            continue
        (args.output / f"{one.ree}.html").write_text(render_html(one, page))
        if args.json:
            (args.output / f"{one.ree}.json").write_text(one.model_dump_json(indent=2))
        if args.provenance:
            (args.output / f"{one.ree}.provenance.txt").write_text(text)
        reviews = f", {one.reviews} review attempts not drawn" if one.reviews else ""
        sys.stdout.write(
            f"{args.output / f'{one.ree}.html'}: {len(one.entries)} entries, assurance {one.verdict}{reviews}\n"
        )
    return 0


def operations(args: argparse.Namespace) -> int:
    """A verification that cannot be drawn is listed as undrawn, never fatal."""
    drawn: list[tuple[str, BehaviourTrace]] = []
    undrawn: list[Undrawn] = []
    for given in args.verifications:
        source = str(given)
        try:
            verified = _Verified.read(given)
        except _UnreadableError as exc:
            undrawn.append(Undrawn(source=source, reason=str(exc)))
            continue
        traces = verified.traces(args.git_executable, count_files=False)  # The catalogue masks counts away.
        if not traces:
            context = verified.dossier.context
            verdict = verified.verification.result.verdict
            reason = "no REE history in this dossier"
            undrawn.append(Undrawn(source=source, test=context.test, verdict=verdict, reason=reason))
        drawn += [(source, one) for one in traces]
    document = build_catalogue(drawn, undrawn).model_dump_json(indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(document)
    else:
        args.output.write_text(document)
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {"trace": trace, "operations": operations}


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return COMMANDS[args.command](args)
