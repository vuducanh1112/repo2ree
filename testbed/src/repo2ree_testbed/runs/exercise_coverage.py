from __future__ import annotations

import argparse
import shutil
import sys

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.exercise_case import CASES, cases, measure, unmeasured


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="measure every case, not only the stale and unmeasured")
    args = parser.parse_args()
    unmatched = 0
    for case in cases(CASES):
        reason = unmeasured(case)
        if reason is None and not args.all:
            continue
        print(reason or f"{case.digest}: measured again", flush=True)
        workdir = run_dir() / "exercises" / execution_id() / "coverage" / case.digest
        shutil.rmtree(workdir, ignore_errors=True)
        measured, differences = measure(case, workdir)
        files = measured.coverage.files if measured.coverage else {}
        print(f"  {sum(len(file.arcs) for file in files.values())} arcs in {len(files)} files", flush=True)
        for difference in differences:
            unmatched += 1
            print(f"  replay differs from the case: {difference}", file=sys.stderr)
    return 1 if unmatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
