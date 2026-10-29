"""``python -m repo2ree_testbed e2e``: run a suite against source stacks, per test or whole."""

from __future__ import annotations

import argparse
import io
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal, get_args

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs.prune import prune
from repo2ree_testbed.runs.schedule import PerTest, Schedule, SuiteRun, WholeSuite
from repo2ree_testbed.stack.clients import Client, Playwright, Script
from repo2ree_testbed.stack.services import Deployment, DockerMode, Mode

type ExitOn = Literal["tests", "run"]


@dataclass(frozen=True)
class Invocation:
    deployment: Deployment
    client: Client
    schedule: Schedule
    # tests: fail when a test did; run: fail only when the run broke, leaving its tests to whoever judges them.
    exit_on: ExitOn = "tests"


class Tee(io.TextIOBase):
    """A console stream that also writes to the run's own log."""

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
    parser.add_argument("--mode", choices=get_args(Mode.__value__), default="provider")
    parser.add_argument("--docker-mode", choices=get_args(DockerMode.__value__), default="dind")
    parser.add_argument("--state-root", type=Path, default=ROOT / "test-artifacts/state")
    parser.add_argument("--exec-bundle", type=Path, default=ROOT / "dist/bundles/exec")
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
    client: Client
    if args.project:
        playwright = Playwright(args.project)
        if (complaint := playwright.accepts()) is not None:
            print(complaint, file=sys.stderr, end="")
            parser.error(f"refusing to start the stack: playwright rejected --project={args.project}")
        client = playwright
    else:
        client = Script(args.script, args.record)
    deployment = Deployment(
        tier=args.project or args.tier,
        compute_locations=args.compute_locations,
        mode=args.mode,
        docker_mode=args.docker_mode,
        state_root=args.state_root,
        exec_bundle=args.exec_bundle,
        tools_bundle=args.tools_bundle,
    )
    schedule = PerTest(args.jobs, select) if args.per_test else WholeSuite()
    return Invocation(deployment, client, schedule, args.exit_on)


def exit_status(status: int, exit_on: ExitOn, completed: bool) -> int:
    """The process's exit code: a run that completed passes ``exit_on="run"`` whatever its tests did."""
    return 0 if exit_on == "run" and completed else status


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    invocation = parse()
    prune()
    run = SuiteRun(invocation.deployment, invocation.client, invocation.schedule)

    def interrupted(_signal: int, _frame: object) -> None:
        run.stop()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    # What this process prints is kept beside the run; its stacks' own processes log to the tests' directories.
    run.root.mkdir(parents=True, exist_ok=True)
    log = (run.root / "tier.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout, sys.stderr = Tee(sys.stdout, log), Tee(sys.stderr, log)
    try:
        return exit_status(run.run(), invocation.exit_on, run.completed)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        run.stop()
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
