"""Run the API showcases on the machines they name."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from repo2ree_testbed.runs import e2e
from repo2ree_testbed.showcases import API_SUITE, ENVIRONMENT_VARIABLE, api_tier, environments_in_use
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName

RUNNER = API_SUITE / "run_api_showcase.py"


def e2e_arguments(environment: EnvironmentName, *, jobs: int, select: Sequence[str] = ()) -> list[str]:
    return [
        *("--script", str(RUNNER)),
        *("--tier", api_tier(environment)),
        *("--environment", environment.value),
        *("--per-test", "--exit-on", "tests"),
        *("--jobs", str(jobs if ENVIRONMENTS[environment].parallel else 1)),
        *(("--select", " ".join(select)) if select else ()),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed api-showcase")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("environments", help="print the machines the API showcases run on")
    run = commands.add_parser("run", help="run the API showcases of one machine")
    run.add_argument("environment", type=EnvironmentName, choices=list(EnvironmentName))
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--select", nargs="*", default=[])
    args = parser.parse_args()

    if args.command == "environments":
        sys.stdout.write("".join(f"{environment}\n" for environment in environments_in_use()))
        return 0
    os.environ[ENVIRONMENT_VARIABLE] = args.environment.value
    return e2e.main(e2e_arguments(args.environment, jobs=args.jobs, select=args.select))


if __name__ == "__main__":
    raise SystemExit(main())
