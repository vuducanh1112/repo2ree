"""Keep test-artifacts bounded; every e2e run prunes first.

Per tier it keeps the newest finished runs, the newest with a problem, the runs the assurance-gate
receipt names, and runs still in progress; old suite folders and stale control state go, and so
do unused bundle-store volumes (never a workbench, which a stack beside this one may hold). A test
case's recording goes once its test has not finished for a month, which is how a renamed or
deleted test's recording leaves; so do session files as old.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from repo2ree_testbed.artifacts import ROOT, domain_dir, run_dir
from repo2ree_testbed.preservation import PreservationManifest
from repo2ree_testbed.records import Receipt, RunRecord, read
from repo2ree_testbed.stack.workbench_cleanup import KEEP_STORES, live_store_volume, stale_store_volumes

RECEIPT = ROOT / ".receipts/assurance-gate.json"
PER_TEST_RUN = re.compile(r"^(?P<tier>.+)-(?P<stamp>\d{8}-\d{6})$")
SUITE_TOKEN = re.compile(r"^e2e-(?P<tier>.+)-[0-9a-f]{32}$")
SUITE_FOLDERS = ("recordings", "archives", "telemetry")
IN_PROGRESS_SECONDS = 6 * 3600
STALE_CONTROL_SECONDS = 24 * 3600
# A test case recording, or a session file, nothing has rewritten for this long belongs to no live test.
STALE_RECORDING_SECONDS = 30 * 24 * 3600


@dataclass(frozen=True)
class Plan:
    remove: list[Path]
    keep: list[Path]


def size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def age(path: Path, now: float) -> float:
    return now - path.stat().st_mtime


def receipt_runs() -> set[Path]:
    receipt = read(Receipt, RECEIPT)
    return {(ROOT / run).resolve() for run in receipt.runs} if receipt else set()


def had_problem(run: Path) -> bool:
    record = read(RunRecord, run / "run.json")
    return record is not None and record.problem()


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


def plan_case_recordings(base: Path, now: float) -> Plan:
    """Each test case recording under ``base`` whose test last finished over a month ago.

    A case is the directory of a manifest the pytest plugin wrote. The walk stops there: what a case
    holds (an REE's own files, its copies) is part of it, and walking it would cost minutes.
    """
    keep: list[Path] = []
    remove: list[Path] = []
    for directory, subdirectories, files in os.walk(base):
        if "manifest.json" not in files:
            continue
        recorded = read(PreservationManifest, Path(directory) / "manifest.json")
        if recorded is None:
            continue
        subdirectories.clear()
        (remove if now - recorded.finished > STALE_RECORDING_SECONDS else keep).append(Path(directory))
    return Plan(sorted(remove), sorted(keep))


def plan_session_files(base: Path, now: float) -> Plan:
    files = sorted(base.glob("*.json")) if base.is_dir() else []
    return Plan([path for path in files if age(path, now) > STALE_RECORDING_SECONDS], [])


def remove_empty_directories(base: Path) -> None:
    """The directories under ``base`` a removal left empty, deepest first."""
    for directory in sorted((path for path in base.rglob("*") if path.is_dir()), key=lambda p: -len(p.parts)):
        if not any(directory.iterdir()):
            directory.rmdir()


def prune_store_volumes(keep_newest: int) -> None:
    try:
        stale = stale_store_volumes(live_store_volume(), keep_newest)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f">> bundle stores not pruned: {error}", file=sys.stderr)
        return
    if stale:
        print(f">> removing {len(stale)} bundle store volume(s), keeping the newest {keep_newest} unused")
        subprocess.run(["docker", "volume", "rm", *stale], check=False, stdout=subprocess.DEVNULL)


def prune(*, keep_runs: int = 5, keep_suite: int = 3, keep_stores: int = KEEP_STORES, dry_run: bool = False) -> None:
    root = run_dir()
    now = time.time()
    recordings = [domain_dir(domain) / "tests" for domain in ("python", "assurance")]
    sessions = [domain_dir(domain) / "sessions" for domain in ("python", "assurance")]
    plans = [
        plan_per_test_runs(root / "e2e", keep_runs, receipt_runs(), now),
        plan_suite_runs(root, keep_suite, now),
        plan_control_state(root, now),
        *(plan_case_recordings(base, now) for base in recordings),
        *(plan_session_files(base, now) for base in sessions),
    ]
    remove = [path for plan in plans for path in plan.remove]
    freed = 0
    for path in remove:
        freed += size(path)
        shown = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"   {'would remove' if dry_run else 'removing'} {shown}")
        if dry_run:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    if not dry_run:
        for base in recordings:
            if base.is_dir():
                remove_empty_directories(base)
    verb = "would free" if dry_run else "freed"
    print(f">> pruned test artifacts: {len(remove)} directories, {verb} {freed / 2**20:.0f} MiB under {root}")
    if not dry_run and shutil.which("docker"):
        prune_store_volumes(keep_stores)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-runs", type=int, default=5, help="per-test runs kept per tier (default 5)")
    parser.add_argument("--keep-suite", type=int, default=3, help="suite runs kept per tier (default 3)")
    parser.add_argument(
        "--keep-stores",
        type=int,
        default=KEEP_STORES,
        help=f"unused bundle stores kept besides the checkout's own (default {KEEP_STORES})",
    )
    parser.add_argument("--dry-run", action="store_true", help="list what would be removed and remove nothing")
    args = parser.parse_args()
    prune(keep_runs=args.keep_runs, keep_suite=args.keep_suite, keep_stores=args.keep_stores, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
