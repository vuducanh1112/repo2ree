#!/usr/bin/env python3
"""Run the system suite against a stack: ``run_system_suite.py --base-url URL [TEST...] [pytest args...]``.

The client ``scripts/test-stack/e2e_stack.py --script`` runs once the stack is up.
With ``--list`` it prints the suite's test ids, one per line, and runs nothing;
given test ids it runs only those (``--per-test`` gives each one a stack of its own).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def listed() -> list[str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = pytest.main([str(HERE), "--collect-only", "-q", "-p", "no:cacheprovider"])
    if status != 0:
        sys.stderr.write(output.getvalue())
        raise SystemExit(status)
    return [line.strip() for line in output.getvalue().splitlines() if "::" in line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url")
    parser.add_argument("--list", action="store_true", help="Print the suite's test ids and run nothing")
    args, rest = parser.parse_known_args()
    os.chdir(ROOT)
    if args.list:
        sys.stdout.write("".join(f"{node}\n" for node in listed()))
        return 0
    if not args.base_url:
        parser.error("--base-url is required to run the suite")
    os.environ["E2E_API_BASE_URL"] = args.base_url
    extra = os.environ.get("E2E_SYSTEM_PYTEST_ARGS", "").split()
    selected = [arg for arg in rest if "::" in arg]
    targets = selected or [str(HERE)]
    options = [arg for arg in rest if arg not in selected]
    # A per-test run names the test's directory; the JUnit report there tells an expected failure from a pass.
    if report_dir := os.environ.get("E2E_TEST_DIR"):
        options.append(f"--junitxml={Path(report_dir) / 'junit.xml'}")
    return int(pytest.main([*targets, "-p", "no:cacheprovider", *extra, *options]))


if __name__ == "__main__":
    sys.exit(main())
