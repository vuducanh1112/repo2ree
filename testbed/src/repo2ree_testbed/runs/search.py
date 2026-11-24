import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from hypothesis import HealthCheck, Phase, given, note, settings, target
from hypothesis.errors import Flaky
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_case import (
    CASES,
    Campaign,
    CampaignSettings,
    KeptCase,
    KeptFor,
    NewArcs,
    NewFeatures,
    SearchName,
    case_of,
    cases,
    checked_out,
    coverage_of,
    covered,
    measure,
    searched,
    unmeasured,
    write,
    write_campaign,
)
from repo2ree_testbed.exercise_features import Feature, ordered
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


type Event = Annotated[Kept | Unconfirmed | RoundEnded, Field(discriminator="event")]
_EVENT: TypeAdapter[Event] = TypeAdapter(Event)


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
    features: frozenset[Feature] = frozenset()
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
        self.features = self.features | {feature for case in found for feature in case.features.features}
        if self.measured:
            self.arcs = arcs_union(self.arcs, covered(found))

    def _judged(self, exercise: Exercise, stage: str) -> Trace:
        workdir = run_dir() / "exercises" / execution_id() / stage / digest(exercise)
        shutil.rmtree(workdir, ignore_errors=True)
        workdir.mkdir(parents=True)
        trace = self.judge(exercise, workdir, self.measured)
        keep(workdir, trace, slim=not stage.startswith("confirm"))
        return trace

    def worth(self, trace: Trace) -> KeptFor | None:
        if self.measured:
            beyond = arcs_without(trace.arcs or {}, self.arcs)
            if arc_count(beyond) >= self.least:
                return NewArcs(files={path: len(pairs) for path, pairs in beyond.items()})
            return None
        fresh = ordered(set(trace.features) - self.features)
        return NewFeatures(features=fresh) if len(fresh) >= self.least else None

    def _steer(self, trace: Trace) -> None:
        if self.measured:
            target(arc_count(arcs_without(trace.arcs or {}, self.arcs)), label="arcs beyond the cases")
        else:
            target(len(set(trace.features) - self.features), label="features beyond the cases")
            target(len(trace.features), label="features covered")

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
        lock = _log().with_name("search.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
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
        self.features = self.features | set(again.features)
        self.arcs = arcs_union(self.arcs, again.arcs or {})
        self.events.append(Kept(worker=self.worker, case=path.stem, steps=len(exercise.steps), kept_for=kept_for))
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


def _log() -> Path:
    return run_dir() / "exercises" / execution_id() / "search.ndjson"


def _record(event: Event) -> None:
    log = _log()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as written:
        written.write(event.model_dump_json() + "\n")


def _events() -> list[Event]:
    log = _log()
    lines = log.read_text().splitlines() if log.is_file() else []
    return [_EVENT.validate_json(line) for line in lines if line]


def summed(campaign: Campaign, events: list[Event], code: int | None) -> Campaign:
    rounds = [event for event in events if isinstance(event, RoundEnded)]
    return campaign.model_copy(
        update={
            "rounds": len(rounds),
            "rounds_found": sum(event.found for event in rounds),
            "unconfirmed": sum(isinstance(event, Unconfirmed) for event in events),
            "kept": tuple(
                KeptCase(case=event.case, kept_for=event.kept_for, steps=event.steps, worker=event.worker)
                for event in events
                if isinstance(event, Kept)
            ),
            "exit": code,
            "ended": datetime.now(UTC) if code is not None else None,
        }
    )


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
                problems = problems or bool(found.trace.problems)
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
    if args.measured:
        return _search(args, until)
    commit, dirty = checked_out()
    settings = CampaignSettings(
        examples=args.examples,
        steps=args.steps,
        keep=args.keep,
        least=args.least,
        hours=args.hours,
        workers=args.workers,
    )
    campaign = Campaign(
        run=execution_id(),
        search=args.search,
        settings=settings,
        commit=commit,
        dirty=dirty,
        machine=os.environ.get("REPO2REE_MACHINE"),
        started=datetime.now(UTC),
    )
    write_campaign(campaign, args.cases)
    code = 1
    try:
        if args.search == "branch-cov":
            measure_stale(args.cases)
        code = _workers(args, until) if args.workers > 1 else _search(args, until)
    finally:
        write_campaign(summed(campaign, _events(), code), args.cases)
    return code


def _search(args: argparse.Namespace, until: float | None) -> int:
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
