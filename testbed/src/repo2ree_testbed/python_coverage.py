"""Combine and render the backend's Python coverage tiers."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from coverage import CoverageData
from pydantic import TypeAdapter

from repo2ree_testbed.artifacts import ROOT, run_dir, write_provenance
from repo2ree_testbed.records import Provenance, read

TIERS = (
    "unit",
    "integration",
    "showcase",
    "e2e-gui-instant",
    "e2e-system",
    "e2e-faults",
    "e2e-chaos",
    "e2e-fuzz",
    "demo-gui",
    "demo-api",
)
_NAMES = TypeAdapter[tuple[str, ...]](tuple[str, ...])


@dataclass(frozen=True)
class CoverageRoot:
    html: Path

    @classmethod
    def current(cls) -> CoverageRoot:
        return cls(run_dir() / "python/coverage")

    @classmethod
    def at(cls, run: Path) -> CoverageRoot:
        return cls(run.resolve() / "python/coverage")

    @property
    def data(self) -> Path:
        return self.html / "data"

    def tier(self, tier: str) -> Path:
        return self.data / tier / ".coverage"


def packages() -> tuple[str, ...]:
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return _NAMES.validate_python(configuration["tool"]["repo2ree"]["workspace"]["backend"])


def integration_packages() -> tuple[str, ...]:
    return tuple(package for package in packages() if (ROOT / package / "tests" / "integration").is_dir())


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


def render(root: CoverageRoot, tier: str) -> None:
    coverage_file = root.tier(tier)
    if not coverage_file.is_file():
        raise RuntimeError(f"no coverage data for the {tier} tier — run it first: one of {' '.join(TIERS)}")
    title = f"repo2ree — {tier} tier, python"
    coverage_command(coverage_file, "html", "-d", str(root.html / tier), "--title", title, quiet=True)
    print(f">> {tier} tier, by module")
    for package in packages():
        include = f"--include={package}/src/*"
        output = str(root.html / tier / "by-module" / package)
        title = f"repo2ree — {package} ({tier} tier, python)"
        coverage_command(coverage_file, "html", include, "-d", output, "--title", title, quiet=True)
        total = coverage_command(coverage_file, "report", include, "--format=total", capture=True)
        print(f"   {package:<15} {total}%")
    total = coverage_command(coverage_file, "report", "--format=total", capture=True)
    print(f"   {'TOTAL':<15} {total}%")
    print(f">> {tier} reports: {root.html}/{tier} (by module: .../by-module/<package>)")


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
        provenance = read(Provenance, path.parent / "provenance.json")
        if provenance is None:
            raise RuntimeError(f"coverage provenance missing: {path}; rerun the test aggregate")
        identities.add(provenance.execution_id)
    if len(identities) != 1:
        raise RuntimeError("coverage belongs to different executions; rerun the tiers together")
    return identities.pop()


def _combine(files: list[Path], destination: Path) -> Path:
    identity = coverage_identity(files)
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)
    coverage_file = destination / ".coverage"
    coverage_command(coverage_file, "combine", "--keep", *(str(path) for path in files))
    write_provenance(destination, identity)
    return coverage_file


def combine_parts(root: CoverageRoot, tier: str, parts: tuple[str, ...]) -> None:
    files = [root.data / f"{tier}-parts" / part / ".coverage" for part in parts]
    missing = [part for part, path in zip(parts, files, strict=True) if not path.is_file()]
    if missing:
        raise RuntimeError(f"{tier} coverage is incomplete; missing: {' '.join(missing)}")
    coverage_file = _combine(files, root.data / tier)
    print(f">> combined {len(files)} {tier} coverage parts: {coverage_file.relative_to(ROOT)}")


def combine(root: CoverageRoot, tiers: tuple[str, ...]) -> None:
    files: list[Path] = []
    included: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    for tier in tiers:
        directory = root.data / tier
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
    coverage_command(_combine(files, root.data / "combined"), "report")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    render_parser = commands.add_parser("render")
    render_parser.add_argument("tier", choices=(*TIERS, "combined", "context"))
    render_parser.add_argument("--run", type=Path, help="run directory; default: this run's")
    combine_parser = commands.add_parser("combine")
    combine_parser.add_argument("--tiers", default="", help="comma-separated tiers; default: every measured tier")
    combine_parser.add_argument("--run", type=Path, help="run directory; default: this run's")
    combine_parser.add_argument("--render", action="store_true", help="render the combined report in the same run")
    commands.add_parser("combine-unit")
    commands.add_parser("combine-integration")
    args = parser.parse_args()
    run: Path | None = args.run if args.command in {"render", "combine"} else None
    root = CoverageRoot.at(run) if run else CoverageRoot.current()
    try:
        if args.command == "render":
            render(root, args.tier)
        elif args.command == "combine-unit":
            combine_parts(root, "unit", packages())
        elif args.command == "combine-integration":
            combine_parts(root, "integration", integration_packages())
        else:
            required = tuple(filter(None, args.tiers.split(",")))
            if unknown := sorted(set(required) - set(TIERS)):
                raise RuntimeError(f"unknown coverage tier: {' '.join(unknown)}")
            if absent := [tier for tier in required if not root.tier(tier).is_file()]:
                raise RuntimeError(f"the run is missing requested coverage tiers: {' '.join(absent)}")
            combine(root, required or TIERS)
            if args.render:
                render(root, "combined")
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
