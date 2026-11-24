from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo2ree_testbed.exercise_case import CASES, cases, unmeasured
from repo2ree_testbed.exercise_measure import measure_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed exercise-coverage")
    parser.add_argument("--all", action="store_true", help="measure every case, not only the stale and unmeasured")
    parser.add_argument("--jobs", type=int, default=1, help="cases replayed side by side, each in its own process")
    parser.add_argument("--cases", type=Path, default=CASES, help="where the cases are")
    args = parser.parse_args(argv)
    chosen = []
    for case in cases(args.cases):
        reason = unmeasured(case)
        if reason is None and not args.all:
            continue
        print(reason or f"{case.digest}: measured again", flush=True)
        chosen.append(case)
    unmatched = 0
    for done in measure_all(chosen, args.cases, "coverage", args.jobs):
        print(f"{done.case.digest}: {done.arcs} arcs in {done.files} files", flush=True)
        for difference in done.differences:
            unmatched += 1
            print(f"  {done.case.digest}: replay differs from the case: {difference}", file=sys.stderr)
    return 1 if unmatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
