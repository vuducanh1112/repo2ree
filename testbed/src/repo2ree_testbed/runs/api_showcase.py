"""Run the showcases on a surface, the API or the command line, each test on a stack on the machine its showcase
names.

python -m repo2ree_testbed api-showcase run      # through the API
python -m repo2ree_testbed cli-showcase run      # the same tests through `ree`, on the machine
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from repo2ree_testbed.runs import e2e
from repo2ree_testbed.showcases import API_SUITE, API_TIER, CLI_TIER, environments_in_use

Surface = Literal["api", "cli"]
RUNNERS: dict[Surface, Path] = {"api": API_SUITE / "run_api_showcase.py", "cli": API_SUITE / "run_cli_showcase.py"}
TIERS: dict[Surface, str] = {"api": API_TIER, "cli": CLI_TIER}


def e2e_arguments(*, jobs: int, select: Sequence[str] = (), surface: Surface = "api") -> list[str]:
    return [
        *("--script", str(RUNNERS[surface])),
        *("--tier", TIERS[surface]),
        *("--per-test", "--exit-on", "tests"),
        *("--jobs", str(jobs)),
        *(("--select", " ".join(select)) if select else ()),
        *(("--no-control-plane",) if surface == "cli" else ()),
    ]


def main(surface: Surface = "api") -> int:
    parser = argparse.ArgumentParser(prog=f"repo2ree_testbed {surface}-showcase")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("environments", help="print the machines the showcases run on")
    run = commands.add_parser("run", help=f"run the showcases through the {surface.upper()}")
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--select", nargs="*", default=[])
    args = parser.parse_args()

    if args.command == "environments":
        sys.stdout.write("".join(f"{environment}\n" for environment in environments_in_use()))
        return 0
    return e2e.main(e2e_arguments(jobs=args.jobs, select=args.select, surface=surface))


if __name__ == "__main__":
    raise SystemExit(main())
