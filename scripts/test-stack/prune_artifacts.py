#!/usr/bin/env python3
"""Keep test-artifacts bounded: ``prune_artifacts.py [--keep-runs N] [--keep-suite N] [--dry-run]``.

Every e2e run adds hundreds of megabytes and nothing removed them. This keeps:

- ``e2e/<tier>-<stamp>/`` (per-test runs): the newest ``--keep-runs`` finished runs of each tier,
  the newest one of each tier with a problem (a test that failed, or passed with
  behaviour that did not), every run the behaviour receipt names, and every run
  still in progress (no ``run.json`` yet, and recent).
- ``recordings/``, ``archives/``, ``telemetry/`` ``<e2e-tier-token>/`` (suite runs):
  the newest ``--keep-suite`` of each tier, and anything recent.
- ``state/control/<token>/``: a stack removes its own once exported; leftovers of
  stacks that did not are removed once stale.

and removes unused bundle-store volumes older than ``--store-days``: only those. (``workbench_cleanup
--store-gc`` also removes every workbench, so it would take down stacks running beside this one.)
e2e_stack.py runs it before every run, so the disk cannot creep up.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/test-stack"))

from test_support.artifacts import run_dir  # noqa: E402
from workbench_cleanup import live_store_volume, stale_store_volumes  # noqa: E402

RECEIPT = ROOT / ".validation-certificates/behaviour-ok"
PER_TEST_RUN = re.compile(r"^(?P<tier>.+)-(?P<stamp>\d{8}-\d{6})$")
SUITE_TOKEN = re.compile(r"^e2e-(?P<tier>.+)-[0-9a-f]{32}$")
SUITE_FOLDERS = ("recordings", "archives", "telemetry")
# Younger than this, a directory may belong to a run still going (one without run.json, or a suite stack).
IN_PROGRESS_SECONDS = 6 * 3600
# A stack's control state outlives it only when its export failed; it is kept this long for debugging.
STALE_CONTROL_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Plan:
    remove: list[Path]
    keep: list[Path]


def size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def age(path: Path, now: float) -> float:
    return now - path.stat().st_mtime


def receipt_runs() -> set[Path]:
    try:
        runs = json.loads(RECEIPT.read_text()).get("runs", [])
    except (OSError, ValueError):
        return set()
    return {(ROOT / run).resolve() for run in runs}


def had_problem(run: Path) -> bool:
    """A test failed, or passed while its behaviour did not (an expected failure's verdict is its own)."""
    try:
        tests = json.loads((run / "run.json").read_text())["tests"]
    except (OSError, ValueError, KeyError):
        return False
    return any(
        test.get("outcome") not in {"passed", "xfailed"}
        or (test.get("outcome") == "passed" and test.get("behaviour") != "passed")
        for test in tests
    )


def plan_per_test_runs(root: Path, keep: int, protected: set[Path], now: float) -> Plan:
    tiers: dict[str, list[Path]] = defaultdict(list)
    for run in root.iterdir() if root.is_dir() else []:
        match = PER_TEST_RUN.match(run.name)
        if match and run.is_dir():
            tiers[match["tier"]].append(run)
    remove: list[Path] = []
    kept: list[Path] = []
    for runs in tiers.values():
        runs.sort(key=lambda run: run.name, reverse=True)
        problem = next((run for run in runs if had_problem(run)), None)
        # The newest finished runs are counted; a run still going is kept besides them.
        finished = [run for run in runs if (run / "run.json").is_file()]
        for run in runs:
            in_progress = run not in finished and age(run, now) < IN_PROGRESS_SECONDS
            newest = run in finished[:keep]
            if newest or run == problem or run.resolve() in protected or in_progress:
                kept.append(run)
            else:
                remove.append(run)
    return Plan(remove, kept)


def plan_suite_runs(root: Path, keep: int, now: float) -> Plan:
    remove: list[Path] = []
    kept: list[Path] = []
    for folder in SUITE_FOLDERS:
        tiers: dict[str, list[Path]] = defaultdict(list)
        base = root / folder
        for path in base.iterdir() if base.is_dir() else []:
            match = SUITE_TOKEN.match(path.name)
            if match and path.is_dir():
                tiers[match["tier"]].append(path)
        for paths in tiers.values():
            paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            for index, path in enumerate(paths):
                (kept if index < keep or age(path, now) < IN_PROGRESS_SECONDS else remove).append(path)
    return Plan(remove, kept)


def plan_control_state(root: Path, now: float) -> Plan:
    base = root / "state/control"
    if not base.is_dir():
        return Plan([], [])
    return Plan([path for path in base.iterdir() if path.is_dir() and age(path, now) > STALE_CONTROL_SECONDS], [])


def prune_store_volumes(days: float) -> None:
    """Unused (dangling) bundle stores older than ``days``, keeping the current bundle's; never a workbench."""
    try:
        stale = stale_store_volumes(days, live_store_volume())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f">> bundle stores not pruned: {error}", file=sys.stderr)
        return
    if stale:
        print(f">> removing {len(stale)} bundle store volume(s) unused for {days:g}d")
        subprocess.run(["docker", "volume", "rm", *stale], check=False, stdout=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-runs", type=int, default=5, help="per-test runs kept per tier (default 5)")
    parser.add_argument("--keep-suite", type=int, default=3, help="suite runs kept per tier (default 3)")
    parser.add_argument("--store-days", type=float, default=14, help="unused bundle stores kept this long (default 14)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be removed and remove nothing")
    args = parser.parse_args()
    root = run_dir()
    now = time.time()
    plans = [
        plan_per_test_runs(root / "e2e", args.keep_runs, receipt_runs(), now),
        plan_suite_runs(root, args.keep_suite, now),
        plan_control_state(root, now),
    ]
    remove = [path for plan in plans for path in plan.remove]
    freed = 0
    for path in remove:
        freed += size(path)
        print(f"   {'would remove' if args.dry_run else 'removing'} {path.relative_to(root)}")
        if not args.dry_run:
            shutil.rmtree(path, ignore_errors=True)
    verb = "would free" if args.dry_run else "freed"
    print(f">> pruned test artifacts: {len(remove)} directories, {verb} {freed / 2**20:.0f} MiB under {root}")
    if not args.dry_run and shutil.which("docker"):
        prune_store_volumes(args.store_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
