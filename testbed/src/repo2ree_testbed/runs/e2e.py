from __future__ import annotations

import argparse
import io
import signal
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import IO, Literal, get_args

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs.prune import prune
from repo2ree_testbed.runs.schedule import PerTest, Schedule, SuiteRun, WholeSuite
from repo2ree_testbed.showcases import gui_machines
from repo2ree_testbed.stack.clients import Client, Playwright, Script
from repo2ree_testbed.stack.environments import ENVIRONMENTS
from repo2ree_testbed.stack.services import Deployment
from repo2ree_testbed.stack.sigstore import SigstoreStack

type ExitOn = Literal["tests", "run"]


@dataclass(frozen=True)
class Invocation:
    deployment: Deployment
    client: Client
    schedule: Schedule
    exit_on: ExitOn = "tests"
    sigstore: bool = False


class Tee(io.TextIOBase):
    def __init__(self, console: IO[str], log: IO[str]) -> None:
        self.console = console
        self.log = log

    def write(self, text: str) -> int:
        self.console.write(text)
        self.log.write(text)
        return len(text)

    def flush(self) -> None:
        self.console.flush()
        self.log.flush()


def positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse(argv: list[str] | None = None) -> Invocation:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed e2e")
    runners = parser.add_mutually_exclusive_group(required=True)
    runners.add_argument("--project", default="")
    runners.add_argument("--script", type=Path)
    parser.add_argument("--tier", default="")
    parser.add_argument("--record", type=Path)
    parser.add_argument("--per-test", action="store_true", help="run each test on a fresh stack of its own")
    parser.add_argument("--compute-locations", type=positive, default=1)
    parser.add_argument("--jobs", type=positive, default=1, help="with --per-test: stacks run side by side")
    parser.add_argument(
        "--select",
        action="append",
        default=None,
        help="with --per-test: run only the tests whose id contains one of these space-separated parts (repeatable)",
    )
    parser.add_argument(
        "--exit-on",
        choices=get_args(ExitOn.__value__),
        default="tests",
        help="tests: exit 1 when a test failed; run: only when the run broke (the assurance gate judges the tests)",
    )
    parser.add_argument(
        "--environment",
        choices=sorted(ENVIRONMENTS),
        help="install each store's workbench on this machine, where it runs the REEs' scripts",
    )
    parser.add_argument(
        "--no-control-plane",
        action="store_true",
        help="start no API and no workbench service: the client runs ree on each test's machine itself",
    )
    parser.add_argument(
        "--sigstore",
        action="store_true",
        help="start a Sigstore of the run's own on the machines' network, for its tests to sign with",
    )
    parser.add_argument("--state-root", type=Path, default=ROOT / "test-artifacts/state")
    parser.add_argument("--cli-bundle", type=Path, default=ROOT / "dist/bundles/cli")
    parser.add_argument("--tools-bundle", type=Path, default=ROOT / "dist/bundles/tools")
    args = parser.parse_args(argv)
    if args.project and args.tier:
        parser.error(f"--tier is implied by --project ({args.project}); drop it")
    if args.record and not args.script:
        parser.error("--record only applies to --script")
    if args.jobs > 1 and not args.per_test:
        parser.error("--jobs runs stacks side by side; it needs --per-test")
    if args.record and args.per_test:
        parser.error("--record records one session; it does not combine with --per-test")
    select = tuple(part for value in args.select or () for part in value.split())
    if select and not args.per_test:
        parser.error("--select picks tests to run each on a stack of its own; it needs --per-test")
    if args.script and not args.tier:
        parser.error("--script needs --tier <name> to say which tier it measures")
    if args.no_control_plane and not (args.script and args.per_test):
        parser.error("--no-control-plane runs a script's tests each on its machine: it needs --script and --per-test")
    client: Client
    if args.project:
        playwright = Playwright(args.project, gui_machines())
        if (complaint := playwright.accepts()) is not None:
            print(complaint, file=sys.stderr, end="")
            parser.error(f"refusing to start the stack: playwright rejected --project={args.project}")
        client = playwright
    else:
        client = Script(args.script, args.record)
    environment = ENVIRONMENTS[args.environment] if args.environment else None
    deployment = Deployment(
        tier=args.project or args.tier,
        compute_locations=args.compute_locations,
        environment=environment,
        state_root=args.state_root,
        cli_bundle=args.cli_bundle,
        tools_bundle=args.tools_bundle,
        control_plane=not args.no_control_plane,
    )
    schedule = PerTest(args.jobs, select) if args.per_test else WholeSuite()
    return Invocation(deployment, client, schedule, args.exit_on, sigstore=args.sigstore)


def exit_status(status: int, exit_on: ExitOn, completed: bool) -> int:
    return 0 if exit_on == "run" and completed else status


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    invocation = parse(argv)
    prune()
    run = SuiteRun(invocation.deployment, invocation.client, invocation.schedule)

    def interrupted(_signal: int, _frame: object) -> None:
        run.stop()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    run.root.mkdir(parents=True, exist_ok=True)
    log = (run.root / "tier.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout, sys.stderr = Tee(sys.stdout, log), Tee(sys.stderr, log)
    sigstore = SigstoreStack(run.root / "sigstore", run.root / "sigstore.log") if invocation.sigstore else None
    try:
        if sigstore is not None:
            run.deployment = replace(run.deployment, sigstore=sigstore.start())
        return exit_status(run.run(), invocation.exit_on, run.completed)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        run.stop()
        if sigstore is not None:
            sigstore.stop()
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
