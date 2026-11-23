import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from hypothesis import HealthCheck, Phase, given, note, settings, target
from hypothesis.errors import Flaky
from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_case import (
    CASES,
    KeptFor,
    NewArcs,
    NewReached,
    SearchName,
    ShowedProblems,
    case_of,
    cases,
    coverage_of,
    covered,
    known,
    measure,
    searched,
    unmeasured,
    write,
)
from repo2ree_testbed.exercise_strategy import exercises
from repo2ree_testbed.exercise_verdict import Arcs, Trace, arc_count, arcs_union, arcs_without, digest, judge, keep

type Judge = Callable[[Exercise, Path, bool], Trace]


def replay(exercise: Exercise, workdir: Path, measured: bool) -> Trace:
    return judge(exercise, workdir, measured=measured)


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Kept(_Model):
    event: Literal["kept"] = "kept"
    worker: int
    case: str
    steps: int
    kept_for: KeptFor


class Unconfirmed(_Model):
    event: Literal["unconfirmed"] = "unconfirmed"
    worker: int
    digest: str
    why: str


class RoundEnded(_Model):
    event: Literal["round"] = "round"
    worker: int
    round: int
    found: bool
    seconds: float


type Event = Kept | Unconfirmed | RoundEnded


class _Found(Exception):  # noqa: N818
    def __init__(self, trace: Trace, kept_for: KeptFor) -> None:
        super().__init__(kept_for.kind)
        self.trace = trace
        self.kept_for = kept_for


@dataclass
class Search:
    search: SearchName
    directory: Path
    examples: int
    steps: int
    least: int
    worker: int = 0
    judge: Judge = replay
    known: frozenset[tuple[str, str, str]] = frozenset()
    reached: frozenset[str] = frozenset()
    arcs: Arcs = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    @property
    def measured(self) -> bool:
        return self.search == "branch-cov"

    @property
    def label(self) -> str:
        return f"{self.search}-{self.worker}"

    def refresh(self) -> None:
        found = cases(self.directory)
        self.known = known(self.directory)
        self.reached = self.reached | {item for case in found for item in case.reached.items}
        if self.measured:
            self.arcs = arcs_union(self.arcs, covered(found))

    def _judged(self, exercise: Exercise, stage: str) -> Trace:
        workdir = run_dir() / "exercises" / execution_id() / stage / digest(exercise)
        shutil.rmtree(workdir, ignore_errors=True)
        workdir.mkdir(parents=True)
        trace = self.judge(exercise, workdir, self.measured)
        keep(workdir, trace)
        return trace

    def worth(self, trace: Trace) -> KeptFor | None:
        if any(problem.known_as not in self.known for problem in trace.problems):
            return ShowedProblems()
        if trace.problems:
            return None
        if self.measured:
            beyond = arcs_without(trace.arcs or {}, self.arcs)
            if arc_count(beyond) >= self.least:
                return NewArcs(files={path: len(pairs) for path, pairs in beyond.items()})
            return None
        fresh = tuple(sorted(set(trace.reached) - self.reached))
        return NewReached(items=fresh) if len(fresh) >= self.least else None

    def _steer(self, trace: Trace) -> None:
        if self.measured:
            target(arc_count(arcs_without(trace.arcs or {}, self.arcs)), label="arcs beyond the cases")
        else:
            target(len(set(trace.reached) - self.reached), label="rules and transitions beyond the cases")
            target(len(trace.reached), label="rules and transitions reached")

    def round(self) -> _Found | None:
        @settings(
            max_examples=self.examples,
            deadline=None,
            database=None,
            phases=(Phase.generate, Phase.target, Phase.shrink),
            suppress_health_check=list(HealthCheck),
            report_multiple_bugs=False,
        )
        @given(exercises(max_steps=self.steps))
        def drawn(exercise: Exercise) -> None:
            note(exercise.model_dump_json(indent=2))
            trace = self._judged(exercise, self.label)
            self._steer(trace)
            kept_for = self.worth(trace)
            if kept_for is not None:
                raise _Found(trace, kept_for)

        try:
            drawn()
        except _Found as found:
            return found
        except Flaky as flaky:
            print(f">> worker {self.worker}: a find did not hold when replayed again: {flaky}", flush=True)
        return None

    def confirm(self, found: _Found) -> Path | None:
        exercise = found.trace.exercise
        again = self._judged(exercise, f"confirm-{self.worker}")
        lock = Path(tempfile.gettempdir()) / f"repo2ree-search-{execution_id()}.lock"
        with lock.open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.refresh()
            kept_for = self.worth(again)
            if kept_for is None or kept_for.kind != found.kept_for.kind:
                self.events.append(
                    Unconfirmed(worker=self.worker, digest=digest(exercise), why=f"replayed again: {kept_for}")
                )
                return None
            coverage = coverage_of(again.arcs) if again.arcs is not None else None
            path = write(case_of(again, searched(self.search, execution_id(), kept_for), coverage), self.directory)
        self.known = self.known | {problem.known_as for problem in again.problems}
        self.reached = self.reached | set(again.reached)
        self.arcs = arcs_union(self.arcs, again.arcs or {})
        self.events.append(Kept(worker=self.worker, case=str(path), steps=len(exercise.steps), kept_for=kept_for))
        return path


def measure_stale(directory: Path) -> None:
    for case in cases(directory):
        reason = unmeasured(case)
        if reason is None:
            continue
        print(f">> {reason}; measuring it", flush=True)
        workdir = run_dir() / "exercises" / execution_id() / "baseline" / case.digest
        shutil.rmtree(workdir, ignore_errors=True)
        measure(case, workdir, directory)


def _record(event: Event) -> None:
    log = run_dir() / "exercises" / execution_id() / "search.ndjson"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as written:
        written.write(event.model_dump_json() + "\n")


def run(search: Search, *, until: float | None, keep_at_most: int) -> int:
    kept = 0
    problems = False
    number = 0
    while kept < keep_at_most:
        number += 1
        search.refresh()
        started = time.monotonic()
        found = search.round()
        _record(
            RoundEnded(worker=search.worker, round=number, found=found is not None, seconds=time.monotonic() - started)
        )
        if found is not None:
            before = len(search.events)
            path = search.confirm(found)
            for event in search.events[before:]:
                _record(event)
            if path is not None:
                kept += 1
                problems = problems or isinstance(found.kept_for, ShowedProblems)
                print(f">> worker {search.worker} kept {path} for {found.kept_for.kind}", flush=True)
        if until is None or time.time() >= until:
            break
    print(f">> worker {search.worker}: {kept} cases kept in {number} rounds", flush=True)
    return 1 if problems else 0


def _workers(args: argparse.Namespace, until: float | None) -> int:
    shared = [args.search, "--examples", str(args.examples), "--steps", str(args.steps)]
    shared += ["--keep", str(args.keep), "--least", str(args.least), "--cases", str(args.cases), "--measured"]
    shared += ["--until", str(until)] if until is not None else []
    environment = {**os.environ, "REPO2REE_TEST_RUN_ID": execution_id()}
    children = [
        subprocess.Popen(
            [sys.executable, "-m", "repo2ree_testbed", "search", *shared, "--worker", str(worker)], env=environment
        )
        for worker in range(args.workers)
    ]
    codes = [child.wait() for child in children]
    return 1 if any(codes) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed search")
    parser.add_argument("search", choices=("spec-cov", "branch-cov"))
    parser.add_argument("--examples", type=int, default=25, help="exercises Hypothesis draws per round")
    parser.add_argument("--steps", type=int, default=30, help="the most steps an exercise has")
    parser.add_argument("--keep", type=int, default=3, help="the most cases each worker keeps")
    parser.add_argument("--least", type=int, default=1, help="the fewest new items (or arcs) a kept case adds")
    parser.add_argument("--hours", type=float, help="search round after round for this long; one round without")
    parser.add_argument("--workers", type=int, default=1, help="searches side by side, each its own process")
    parser.add_argument("--cases", type=Path, default=CASES, help="where the cases are, and kept ones go")
    parser.add_argument("--worker", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--until", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--measured", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    until = args.until if args.until is not None else (time.time() + args.hours * 3600 if args.hours else None)
    if args.search == "branch-cov" and not args.measured:
        measure_stale(args.cases)
    if args.workers > 1:
        return _workers(args, until)
    search = Search(
        search=args.search,
        directory=args.cases,
        examples=args.examples,
        steps=args.steps,
        least=args.least,
        worker=args.worker,
    )
    return run(search, until=until, keep_at_most=args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
