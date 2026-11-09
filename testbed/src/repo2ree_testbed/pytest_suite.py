"""A pytest suite as a stack's client: ``--list`` prints its test ids; given ids, it runs only those."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import ROOT


def listed(*directories: Path) -> list[str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = pytest.main([*map(str, directories), "--collect-only", "-q", "-p", "no:cacheprovider"])
    if status != 0:
        sys.stderr.write(output.getvalue())
        raise SystemExit(status)
    return [line.strip() for line in output.getvalue().splitlines() if "::" in line]


def run(*directories: Path) -> int:
    names = ", ".join(str(directory.relative_to(ROOT)) for directory in directories)
    parser = argparse.ArgumentParser(description=f"Run {names} against a stack")
    parser.add_argument("--base-url")
    parser.add_argument("--list", action="store_true", help="print the suite's test ids and run nothing")
    args, rest = parser.parse_known_args()
    os.chdir(ROOT)
    if args.list:
        sys.stdout.write("".join(f"{node}\n" for node in listed(*directories)))
        return 0
    if not args.base_url:
        parser.error("--base-url is required to run the suite")
    os.environ["E2E_API_BASE_URL"] = args.base_url
    selected = [arg for arg in rest if "::" in arg]
    options = [arg for arg in rest if arg not in selected]
    if report_dir := os.environ.get("E2E_TEST_DIR"):
        options.append(f"--junitxml={Path(report_dir) / 'junit.xml'}")
    extra = os.environ.get("E2E_SYSTEM_PYTEST_ARGS", "").split()
    targets = selected or [str(directory) for directory in directories]
    return int(pytest.main([*targets, "-p", "no:cacheprovider", *extra, *options]))
