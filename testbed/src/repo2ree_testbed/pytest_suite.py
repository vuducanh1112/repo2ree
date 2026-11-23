from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from collections.abc import Callable
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


def run(*directories: Path, machine: Callable[[str], str] | None = None) -> int:
    names = ", ".join(str(directory.relative_to(ROOT)) for directory in directories)
    parser = argparse.ArgumentParser(description=f"Run {names} against a stack")
    parser.add_argument("--base-url", help="the stack's API; a stack with no control plane has none")
    parser.add_argument("--list", action="store_true", help="print the suite's test ids and run nothing")
    args, rest = parser.parse_known_args()
    os.chdir(ROOT)
    if args.list:
        nodes = listed(*directories)
        sys.stdout.write("".join(f"{node}\t{machine(node)}\n" if machine else f"{node}\n" for node in nodes))
        return 0
    if args.base_url:
        os.environ["E2E_API_BASE_URL"] = args.base_url
    selected = [arg for arg in rest if "::" in arg]
    options = [arg for arg in rest if arg not in selected]
    if report_dir := os.environ.get("E2E_TEST_DIR"):
        options.append(f"--junitxml={Path(report_dir) / 'junit.xml'}")
    extra = os.environ.get("E2E_SYSTEM_PYTEST_ARGS", "").split()
    targets = selected or [str(directory) for directory in directories]
    return int(pytest.main([*targets, "-p", "no:cacheprovider", *extra, *options]))
