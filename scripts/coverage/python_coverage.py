#!/usr/bin/env python3
"""Render and combine Python coverage tiers."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from coverage import CoverageData

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "test-artifacts/coverage/python/data"
HTML_DIR = ROOT / "test-artifacts/coverage/python"
TIERS = ("unit", "integration", "e2e-gui", "e2e-gui-review", "demo-gui", "demo-api", "demo-gui-code-ocean")
UNIT_PARTS = ("protocol", "core", "api", "supervisor", "executor", "docker-support", "provider", "workbench")


def packages() -> tuple[str, ...]:
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return tuple(configuration["tool"]["uv"]["workspace"]["members"])


def coverage_command(coverage_file: Path, *args: str, capture: bool = False, quiet: bool = False) -> str:
    result = subprocess.run(
        ["coverage", *args],
        check=True,
        cwd=ROOT,
        env={**os.environ, "COVERAGE_FILE": str(coverage_file)},
        capture_output=capture,
        stdout=subprocess.DEVNULL if quiet and not capture else None,
        text=True,
    )
    return result.stdout.strip() if capture else ""


def render(tier: str) -> None:
    coverage_file = DATA_DIR / tier / ".coverage"
    if not coverage_file.is_file():
        raise RuntimeError(f"no coverage data for the {tier} tier — run it first: one of {' '.join(TIERS)}")
    coverage_command(
        coverage_file,
        "html",
        "-d",
        str(HTML_DIR / tier),
        "--title",
        f"repo2ree — {tier} tier, python",
        quiet=True,
    )
    print(f">> {tier} tier, by module")
    for package in packages():
        include = f"{package}/src/*"
        coverage_command(
            coverage_file,
            "html",
            f"--include={include}",
            "-d",
            str(HTML_DIR / tier / "by-module" / package),
            "--title",
            f"repo2ree — {package} ({tier} tier, python)",
            quiet=True,
        )
        total = coverage_command(coverage_file, "report", f"--include={include}", "--format=total", capture=True)
        print(f"   {package:<15} {total}%")
    total = coverage_command(coverage_file, "report", "--format=total", capture=True)
    print(f"   {'TOTAL':<15} {total}%")
    print(f">> {tier} reports: {HTML_DIR.relative_to(ROOT)}/{tier} (by module: .../by-module/<package>)")


def tier_matches_tree(directory: Path) -> bool:
    for data_file in sorted(directory.glob(".coverage*")):
        data = CoverageData(basename=str(data_file))
        data.read()
        if any(not Path(measured).exists() for measured in data.measured_files()):
            return False
    return True


def combine_unit() -> None:
    parts_dir = DATA_DIR / "unit-parts"
    files = [parts_dir / part / ".coverage" for part in UNIT_PARTS]
    missing = [part for part, path in zip(UNIT_PARTS, files, strict=True) if not path.is_file()]
    if missing:
        raise RuntimeError(f"unit coverage is incomplete; missing: {' '.join(missing)}")

    unit_dir = DATA_DIR / "unit"
    shutil.rmtree(unit_dir, ignore_errors=True)
    unit_dir.mkdir(parents=True)
    coverage_file = unit_dir / ".coverage"
    coverage_command(coverage_file, "combine", "--keep", *(str(path) for path in files))
    print(f">> combined {len(files)} unit coverage parts: {coverage_file.relative_to(ROOT)}")


def combine() -> None:
    files: list[Path] = []
    included: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    for tier in TIERS:
        directory = DATA_DIR / tier
        found = sorted(directory.glob(".coverage*"))
        if not found:
            missing.append(tier)
        elif tier_matches_tree(directory):
            files.extend(found)
            included.append(tier)
        else:
            stale.append(tier)
    if not files:
        raise RuntimeError("no tier has been measured; run e.g. 'just test-backend-unit' first")
    print(f">> combined: {' '.join(included)}")
    if missing:
        print(f">> NOT included (never measured on this tree): {' '.join(missing)}")
    if stale:
        print(f">> NOT included (measured against an older tree — re-run to refresh): {' '.join(stale)}")
    combined_dir = DATA_DIR / "combined"
    shutil.rmtree(combined_dir, ignore_errors=True)
    combined_dir.mkdir(parents=True)
    coverage_file = combined_dir / ".coverage"
    coverage_command(coverage_file, "combine", "--keep", *(str(path) for path in files))
    coverage_command(coverage_file, "report")
    render("combined")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("tier")
    commands.add_parser("combine")
    commands.add_parser("combine-unit")
    args = parser.parse_args()
    try:
        if args.command == "render":
            render(args.tier)
        elif args.command == "combine-unit":
            combine_unit()
        else:
            combine()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
