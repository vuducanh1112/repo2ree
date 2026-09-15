#!/usr/bin/env python3
"""Render and combine backend Python coverage tiers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from coverage import CoverageData

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from test_support.artifacts import ARTIFACTS, run_dir, write_provenance  # noqa: E402

DATA_DIR = run_dir() / "python/coverage/data"
HTML_DIR = run_dir() / "python/coverage"
TIERS = ("unit", "integration", "e2e-gui", "e2e-gui-review", "demo-gui", "demo-api", "demo-gui-code-ocean")


def packages() -> tuple[str, ...]:
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return tuple(configuration["tool"]["repo2ree"]["workspace"]["backend"])


UNIT_PARTS = packages()
INTEGRATION_PARTS = tuple(package for package in UNIT_PARTS if (ROOT / package / "tests" / "integration").is_dir())


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
    print(f">> {tier} reports: {HTML_DIR}/{tier} (by module: .../by-module/<package>)")


def tier_matches_tree(directory: Path) -> bool:
    for data_file in sorted(directory.glob(".coverage*")):
        data = CoverageData(basename=str(data_file))
        data.read()
        if any(not Path(measured).exists() for measured in data.measured_files()):
            return False
    return True


def coverage_identity(files: list[Path]) -> str:
    identities = set()
    for path in files:
        metadata = path.parent / "provenance.json"
        if not metadata.is_file():
            # Archived run directories predate explicit provenance sidecars.
            try:
                archived = path.relative_to(ARTIFACTS / "runs")
            except ValueError:
                raise RuntimeError(f"coverage provenance missing: {path}; rerun the test aggregate") from None
            identities.add(f"archived:{archived.parts[0]}")
        else:
            identities.add(json.loads(metadata.read_text())["execution_id"])
    if len(identities) != 1:
        raise RuntimeError("coverage belongs to different executions; rerun the tiers together")
    return str(next(iter(identities)))


def combine_parts(tier: str, parts: tuple[str, ...]) -> None:
    parts_dir = DATA_DIR / f"{tier}-parts"
    files = [parts_dir / part / ".coverage" for part in parts]
    missing = [part for part, path in zip(parts, files, strict=True) if not path.is_file()]
    if missing:
        raise RuntimeError(f"{tier} coverage is incomplete; missing: {' '.join(missing)}")

    identity = coverage_identity(files)
    tier_dir = DATA_DIR / tier
    shutil.rmtree(tier_dir, ignore_errors=True)
    tier_dir.mkdir(parents=True)
    coverage_file = tier_dir / ".coverage"
    coverage_command(coverage_file, "combine", "--keep", *(str(path) for path in files))
    write_provenance(tier_dir, identity)
    print(f">> combined {len(files)} {tier} coverage parts: {coverage_file.relative_to(ROOT)}")


def combine_unit() -> None:
    combine_parts("unit", UNIT_PARTS)


def combine_integration() -> None:
    combine_parts("integration", INTEGRATION_PARTS)


def combine(tiers: tuple[str, ...] = TIERS) -> None:
    files: list[Path] = []
    included: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    for tier in tiers:
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
    identity = coverage_identity(files)
    combined_dir = DATA_DIR / "combined"
    shutil.rmtree(combined_dir, ignore_errors=True)
    combined_dir.mkdir(parents=True)
    coverage_file = combined_dir / ".coverage"
    coverage_command(coverage_file, "combine", "--keep", *(str(path) for path in files))
    write_provenance(combined_dir, identity)
    coverage_command(coverage_file, "report")


def select_reporting_run(tiers: tuple[str, ...], explicit: Path | None = None) -> Path:
    """Select one recorded run; never assemble tiers from unrelated runs."""
    if explicit is not None:
        return explicit.resolve()
    requested = tiers or TIERS
    current = DATA_DIR.parents[2]
    if any((DATA_DIR / tier / ".coverage").is_file() for tier in (*TIERS, "combined", "context")):
        return current
    candidates = []
    for root in (ARTIFACTS / "runs").glob("*"):
        files = [root / "coverage/python/data" / tier / ".coverage" for tier in requested]
        present = [path for path in files if path.is_file()]
        if present and (not tiers or len(present) == len(files)):
            candidates.append((max(path.stat().st_mtime_ns for path in present), root))
    if not candidates:
        raise RuntimeError(
            "no recorded run contains the requested coverage tiers; run the matching test aggregate first"
        )
    return max(candidates)[1]


def use_reporting_run(root: Path) -> None:
    global DATA_DIR, HTML_DIR
    HTML_DIR = root / "python/coverage"
    if not HTML_DIR.exists() and (root / "coverage/python").exists():
        HTML_DIR = root / "coverage/python"
    DATA_DIR = HTML_DIR / "data"
    print(f">> coverage run: {root}")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("tier", choices=(*TIERS, "combined", "context"))
    render_parser.add_argument(
        "--run", type=Path, help="recorded run directory; default: current or latest suitable run"
    )
    combine_parser = commands.add_parser("combine")
    combine_parser.add_argument("--tiers", default="", help="comma-separated tiers; default: every measured tier")
    combine_parser.add_argument(
        "--run", type=Path, help="recorded run directory; default: current or latest suitable run"
    )
    combine_parser.add_argument("--render", action="store_true", help="render the combined report in the same run")
    commands.add_parser("combine-unit")
    commands.add_parser("combine-integration")
    args = parser.parse_args()
    try:
        if args.command == "render":
            use_reporting_run(select_reporting_run((args.tier,), args.run))
            render(args.tier)
        elif args.command == "combine-unit":
            combine_unit()
        elif args.command == "combine-integration":
            combine_integration()
        else:
            tiers = tuple(filter(None, args.tiers.split(","))) or TIERS
            unknown = sorted(set(tiers) - set(TIERS))
            if unknown:
                raise RuntimeError(f"unknown coverage tier: {' '.join(unknown)}")
            required = tuple(filter(None, args.tiers.split(",")))
            use_reporting_run(select_reporting_run(required, args.run))
            if required and any(not (DATA_DIR / tier / ".coverage").is_file() for tier in required):
                raise RuntimeError(
                    "selected run is missing requested coverage tiers; refusing an incomplete combination"
                )
            combine(tiers)
            if args.render:
                render("combined")
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
