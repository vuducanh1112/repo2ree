import argparse
import json
import subprocess
import sys
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from repo2ree_testbed.artifacts import ROOT, run_dir
from repo2ree_testbed.cli_session import CliCommand
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_behaviours import Behaviour, declared
from repo2ree_testbed.exercise_case import (
    CASES,
    Campaign,
    CaseBehaviours,
    ExerciseCase,
    Expectation,
    Origin,
    campaigns,
    cases,
)
from repo2ree_testbed.exercise_verdict import Arcs, Problem, Trace, arcs_union, arcs_without
from repo2ree_testbed.runs import session


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StepRun(_Model):
    step: int
    ree: str
    operation: str
    words: tuple[str, ...] | None
    exit: int | None
    status: str | None
    failure: str | None
    scope: str | None
    commit: str | None
    changed: bool | None


class Replay(_Model):
    workdir: str
    when: datetime
    spec_digest: str
    problems: tuple[Problem, ...]
    behaviours: tuple[Behaviour, ...]
    steps: tuple[StepRun, ...]
    session: str


class CoveredFile(_Model):
    path: str
    arcs: int
    unique: int
    stale: bool


class CoverageSummary(_Model):
    commit: str
    dirty: bool
    files: tuple[CoveredFile, ...]


class CaseExport(_Model):
    digest: str
    exercise: Exercise
    origin: Origin
    expects: Expectation
    behaviours: CaseBehaviours
    unique_behaviours: tuple[Behaviour, ...]
    coverage: CoverageSummary | None
    replay: Replay | None


class ExercisesExport(_Model):
    format: Literal["repo2ree-exercises/1"] = "repo2ree-exercises/1"
    campaigns: tuple[Campaign, ...]
    declared: tuple[Behaviour, ...]
    cases: tuple[CaseExport, ...]


def held_in(workdir: Path) -> Iterator[tuple[str, str, Path]]:
    for root in sorted((workdir / "rees").iterdir()):
        if (root / ".git").is_dir():
            yield root.name, "", root
        for review in sorted((root / "reviews").glob("*")):
            if (review / ".git").is_dir():
                yield root.name, f"reviews/{review.name}/", review


def commands(trace: Trace) -> tuple[CliCommand, ...]:
    found: list[CliCommand] = []
    for replayed in trace.replayed:
        step = trace.exercise.steps[replayed.step]
        exporter = getattr(step, "exported_by", replayed.ree)
        found.extend(
            CliCommand(
                ree=exporter if ran.words[:1] == ("bundle",) else replayed.ree,
                words=ran.words,
                exit=ran.exit,
                result=ran.result if isinstance(ran.result, dict) else None,
                log=ran.log,
                started=ran.started,
                finished=ran.finished,
            )
            for ran in (*replayed.prepared, *((replayed.ran,) if replayed.ran else ()))
        )
    return tuple(found)


def session_page(workdir: Path, trace: Trace) -> Path:
    found, unmatched = session.steps(commands(trace), held_in(workdir))
    page = workdir / "session" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(session.render(f"exercise {trace.digest}", found, unmatched), encoding="utf-8")
    return page


def _field(value: JsonValue, *names: str) -> JsonValue:
    for name in names:
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value


def replay_of(workdir: Path, trace: Trace) -> Replay:
    steps: list[StepRun] = []
    for replayed in trace.replayed:
        result = replayed.ran.result if replayed.ran is not None else None
        history = _field(result, "history")
        scope = _field(history, "scope")
        after = _field(history, "after_snapshot_id")
        failure = _field(result, "failure", "message")
        status = _field(result, "status")
        changed = _field(history, "changed")
        steps.append(
            StepRun(
                step=replayed.step,
                ree=replayed.ree,
                operation=replayed.operation,
                words=replayed.ran.words if replayed.ran is not None else None,
                exit=replayed.ran.exit if replayed.ran is not None else None,
                status=status if isinstance(status, str) else None,
                failure=failure if isinstance(failure, str) else None,
                scope=scope if isinstance(scope, str) else None,
                commit=after if isinstance(after, str) else None,
                changed=changed if isinstance(changed, bool) else None,
            )
        )
    return Replay(
        workdir=_from_root(workdir),
        when=datetime.fromtimestamp((workdir / "trace.json").stat().st_mtime, UTC),
        spec_digest=trace.spec_digest,
        problems=trace.problems,
        behaviours=trace.behaviours,
        steps=tuple(steps),
        session=_from_root(session_page(workdir, trace)),
    )


def _from_root(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _trace(workdir: Path) -> Trace | None:
    try:
        return Trace.model_validate_json((workdir / "trace.json").read_text())
    except ValidationError:
        return None


def newest_replay(runs: Path, digest: str) -> tuple[Path, Trace] | None:
    found = [trace.parent for trace in runs.glob(f"*/*/{digest}/trace.json") if (trace.parent / "rees").is_dir()]
    for workdir in sorted(found, key=lambda workdir: (workdir / "trace.json").stat().st_mtime, reverse=True):
        if (trace := _trace(workdir)) is not None:
            return workdir, trace
    return None


def specified() -> tuple[Behaviour, ...]:
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "export"]
    return declared(json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout))


def _coverage(case: ExerciseCase, others: Arcs) -> CoverageSummary | None:
    if case.coverage is None:
        return None
    stale = set(case.coverage.stale())
    unique = arcs_without(case.coverage.arcs, others)
    return CoverageSummary(
        commit=case.coverage.commit,
        dirty=case.coverage.dirty,
        files=tuple(
            CoveredFile(path=path, arcs=len(covered.arcs), unique=len(unique.get(path, ())), stale=path in stale)
            for path, covered in sorted(case.coverage.files.items())
        ),
    )


def exported(
    found: Sequence[ExerciseCase], recorded: Sequence[Campaign], runs: Path, declared: tuple[Behaviour, ...] = ()
) -> ExercisesExport:
    exports = []
    for case in found:
        others = [other for other in found if other.digest != case.digest]
        covered_elsewhere = {behaviour for other in others for behaviour in other.behaviours.behaviours}
        arcs_elsewhere: Arcs = {}
        for other in others:
            if other.coverage is not None:
                arcs_elsewhere = arcs_union(arcs_elsewhere, other.coverage.arcs)
        newest = newest_replay(runs, case.digest)
        replay = replay_of(*newest) if newest is not None else None
        exports.append(
            CaseExport(
                digest=case.digest,
                exercise=case.exercise,
                origin=case.origin,
                expects=case.expects,
                behaviours=case.behaviours,
                unique_behaviours=tuple(
                    behaviour for behaviour in case.behaviours.behaviours if behaviour not in covered_elsewhere
                ),
                coverage=_coverage(case, arcs_elsewhere),
                replay=replay,
            )
        )
    return ExercisesExport(campaigns=tuple(recorded), declared=declared, cases=tuple(exports))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed exercise-export")
    parser.add_argument("-o", "--output", type=Path, required=True, help="write the export here")
    parser.add_argument("--cases", type=Path, default=CASES, help="where the cases and their campaigns are")
    args = parser.parse_args(argv)
    export = exported(cases(args.cases), campaigns(args.cases), run_dir() / "exercises", specified())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(export.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
