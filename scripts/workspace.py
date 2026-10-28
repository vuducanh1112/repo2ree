#!/usr/bin/env python3
"""The Python workspace's packages, as `pyproject.toml` declares them, for recipes to loop over.

- ``backend``, ``assurance``, ``tooling`` print the packages of one role
  (``[tool.repo2ree.workspace]``); ``members`` prints every package (``[tool.uv.workspace]``).
  With ``--src``, each package's sources instead (``<package>/src``).
- ``suites TIER [PACKAGE...]`` prints the suites of the tier, ``unit`` or ``integration``, for
  the packages given (the backend's by default). A package's unit suite is its
  ``tests/unit``, or its ``tests`` when it has no tiers; one without ``tests/integration``
  has no integration suite.

A package added to the workspace is checked, tested, and measured without a recipe of its
own. The roles must divide the members between them, or this refuses to answer.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("backend", "assurance", "tooling")


def roles(config: dict[str, Any]) -> dict[str, list[str]]:
    declared = config["tool"]["repo2ree"]["workspace"]
    by_role = {role: list(declared[role]) for role in ROLES}
    members = list(config["tool"]["uv"]["workspace"]["members"])
    assigned = [package for packages in by_role.values() for package in packages]
    if Counter(assigned) != Counter(members):
        raise ValueError(
            "[tool.repo2ree.workspace] must give every workspace member exactly one role\n"
            f"  members:  {' '.join(members)}\n  assigned: {' '.join(assigned)}"
        )
    return {**by_role, "members": members}


def suites(root: Path, tier: str, packages: Sequence[str]) -> list[str]:
    found = []
    for package in packages:
        tests = root / package / "tests"
        if (tests / tier).is_dir():
            found.append(f"{package}/tests/{tier}")
        elif tier == "unit" and tests.is_dir():
            found.append(f"{package}/tests")
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for role in (*ROLES, "members"):
        commands.add_parser(role).add_argument("--src", action="store_true")
    tiers = commands.add_parser("suites")
    tiers.add_argument("tier", choices=("unit", "integration"))
    tiers.add_argument("packages", nargs="*")
    args = parser.parse_args(argv)
    try:
        packages = roles(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if args.command == "suites":
        print(*suites(ROOT, args.tier, args.packages or packages["backend"]))
    else:
        print(*(f"{package}/src" if args.src else package for package in packages[args.command]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
