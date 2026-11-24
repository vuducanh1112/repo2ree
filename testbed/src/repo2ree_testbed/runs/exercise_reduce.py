import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from repo2ree_testbed.exercise_behaviours import Behaviour
from repo2ree_testbed.exercise_case import CASES, COVERAGE, ExerciseCase, HandWritten, cases, unmeasured

type Arc = tuple[str, int, int]
type Ground = frozenset[Behaviour | Arc]


def ground(case: ExerciseCase) -> Ground:
    arcs = (
        {(path, start, end) for path, pairs in case.coverage.arcs.items() for start, end in pairs}
        if case.coverage is not None
        else set()
    )
    return frozenset({*case.behaviours.behaviours, *arcs})


@dataclass(frozen=True)
class Reduction:
    kept: tuple[ExerciseCase, ...]
    removed: tuple[ExerciseCase, ...]


def reduce(found: Sequence[ExerciseCase]) -> Reduction:
    fixed = [case for case in found if isinstance(case.origin, HandWritten)]
    searched = sorted(
        (case for case in found if not isinstance(case.origin, HandWritten)),
        key=lambda case: (len(case.exercise.steps), case.digest),
    )
    grounds = {case.digest: ground(case) for case in found}
    held: set[Behaviour | Arc] = set().union(*(grounds[case.digest] for case in fixed))
    wanted = set().union(*(grounds[case.digest] for case in searched)) - held
    chosen: list[ExerciseCase] = []
    while wanted:
        best = max(searched, key=lambda case: len(grounds[case.digest] & wanted))
        chosen.append(best)
        wanted -= grounds[best.digest]
        held |= grounds[best.digest]
    for case in sorted(chosen, key=lambda case: (-len(case.exercise.steps), case.digest)):
        others = [other for other in [*fixed, *chosen] if other is not case]
        if grounds[case.digest] <= set().union(*(grounds[other.digest] for other in others)):
            chosen.remove(case)
    kept = {case.digest for case in [*fixed, *chosen]}
    survivors = tuple(case for case in found if case.digest in kept)
    removed = tuple(case for case in found if case.digest not in kept)
    return Reduction(kept=survivors, removed=removed)


def remove(case: ExerciseCase, directory: Path) -> None:
    (directory / f"{case.digest}.json").unlink()
    (directory / COVERAGE / f"{case.digest}.json").unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed exercise-reduce")
    parser.add_argument("--cases", type=Path, default=CASES, help="where the cases are")
    parser.add_argument("--dry-run", action="store_true", help="say which cases would go, and remove none")
    args = parser.parse_args(argv)
    found = cases(args.cases)
    if stale := [reason for case in found if (reason := unmeasured(case)) is not None]:
        for reason in stale:
            print(f">> {reason}", file=sys.stderr)
        print(">> measure them first: just re-measure-exercises", file=sys.stderr)
        return 1
    reduction = reduce(found)
    for case in reduction.removed:
        print(f">> {case.digest} ({len(case.exercise.steps)} steps) covers nothing the kept cases do not", flush=True)
        if not args.dry_run:
            remove(case, args.cases)
    verb = "would keep" if args.dry_run else "kept"
    print(f">> {verb} {len(reduction.kept)} of {len(found)} cases", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
