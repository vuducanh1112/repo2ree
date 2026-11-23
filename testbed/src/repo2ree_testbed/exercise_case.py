from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_verdict import (
    Arcs,
    Problem,
    Trace,
    arcs_union,
    digest,
    judge,
    keep,
)

CASES: Final = ROOT / "exercises"
COVERAGE: Final = "coverage"
CAMPAIGNS: Final = "campaigns"

SearchName = Literal["spec-cov", "branch-cov"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _git(*words: str) -> str:
    return subprocess.run(["git", *words], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def checked_out() -> tuple[str, bool]:
    return _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain"))


def blobs(paths: Sequence[str]) -> dict[str, str | None]:
    present = [path for path in paths if (ROOT / path).is_file()]
    hashed = _git("hash-object", "--", *present).splitlines() if present else []
    return {path: dict(zip(present, hashed, strict=True)).get(path) for path in paths}


class HandWritten(_Model):
    kind: Literal["hand_written"] = "hand_written"


class ShowedProblems(_Model):
    kind: Literal["showed_problems"] = "showed_problems"


class NewArcs(_Model):
    kind: Literal["new_arcs"] = "new_arcs"
    files: dict[str, int]


class NewReached(_Model):
    kind: Literal["new_reached"] = "new_reached"
    items: tuple[str, ...]


type KeptFor = Annotated[ShowedProblems | NewArcs | NewReached, Field(discriminator="kind")]


class Searched(_Model):
    kind: Literal["searched"] = "searched"
    search: SearchName
    run: str
    commit: str
    dirty: bool
    kept_for: KeptFor


type Origin = Annotated[HandWritten | Searched, Field(discriminator="kind")]


class Conforms(_Model):
    kind: Literal["conforms"] = "conforms"


class Shows(_Model):
    kind: Literal["shows"] = "shows"
    problems: tuple[Problem, ...] = Field(min_length=1)


type Expectation = Annotated[Conforms | Shows, Field(discriminator="kind")]


class Reached(_Model):
    spec_digest: str
    items: tuple[str, ...]


class CoveredFile(_Model):
    blob: str
    arcs: tuple[tuple[int, int], ...]


class CaseCoverage(_Model):
    commit: str
    dirty: bool
    files: dict[str, CoveredFile]

    @property
    def arcs(self) -> Arcs:
        return {path: covered.arcs for path, covered in self.files.items()}

    def stale(self) -> tuple[str, ...]:
        now = blobs(tuple(self.files))
        return tuple(path for path, covered in self.files.items() if now[path] != covered.blob)


def coverage_of(arcs: Arcs) -> CaseCoverage:
    commit, dirty = checked_out()
    held = blobs(tuple(arcs))
    files = {path: CoveredFile(blob=blob, arcs=pairs) for path, pairs in arcs.items() if (blob := held[path])}
    return CaseCoverage(commit=commit, dirty=dirty, files=files)


class ExerciseCase(_Model):
    exercise: Exercise
    origin: Origin
    expects: Expectation
    reached: Reached
    coverage: CaseCoverage | None = Field(default=None, exclude=True)

    @property
    def digest(self) -> str:
        return digest(self.exercise)


def case_of(trace: Trace, origin: Origin, coverage: CaseCoverage | None = None) -> ExerciseCase:
    expects: Expectation = Shows(problems=trace.problems) if trace.problems else Conforms()
    reached = Reached(spec_digest=trace.spec_digest, items=trace.reached)
    return ExerciseCase(exercise=trace.exercise, origin=origin, expects=expects, reached=reached, coverage=coverage)


def write(case: ExerciseCase, directory: Path = CASES) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{case.digest}.json"
    path.write_text(case.model_dump_json(indent=2, exclude_none=True) + "\n")
    if case.coverage is not None:
        write_coverage(case.digest, case.coverage, directory)
    return path


def write_coverage(name: str, coverage: CaseCoverage, directory: Path = CASES) -> Path:
    path = directory / COVERAGE / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(coverage.model_dump_json() + "\n")
    return path


def cases(directory: Path = CASES) -> tuple[ExerciseCase, ...]:
    found = []
    for path in sorted(directory.glob("*.json")):
        case = ExerciseCase.model_validate_json(path.read_text())
        measured = directory / COVERAGE / path.name
        if measured.is_file():
            case = case.model_copy(update={"coverage": CaseCoverage.model_validate_json(measured.read_text())})
        found.append(case)
    return tuple(found)


def measure(case: ExerciseCase, workdir: Path, directory: Path = CASES) -> tuple[ExerciseCase, list[str]]:
    trace = judge(case.exercise, workdir, measured=True)
    keep(workdir, trace)
    measured = case.model_copy(update={"coverage": coverage_of(trace.arcs or {})})
    if measured.coverage is not None:
        write_coverage(case.digest, measured.coverage, directory)
    return measured, unmet(case, trace)


def known(directory: Path = CASES) -> frozenset[tuple[str, str, str]]:
    return frozenset(
        problem.known_as
        for case in cases(directory)
        if isinstance(case.expects, Shows)
        for problem in case.expects.problems
    )


def covered(found: Sequence[ExerciseCase]) -> Arcs:
    together: Arcs = {}
    for case in found:
        if case.coverage is not None:
            together = arcs_union(together, case.coverage.arcs)
    return together


def unmet(case: ExerciseCase, trace: Trace) -> list[str]:
    if isinstance(case.expects, Conforms):
        return [f"shown, though the case conforms: {problem}" for problem in trace.problems]
    if not trace.problems:
        return ["stale: the exercise conforms now; change the case to expect it to conform, in a commit of its own"]
    shown = {problem.key: problem for problem in trace.problems}
    kept = {problem.key: problem for problem in case.expects.problems}
    return [f"no longer shown: {kept[key]}" for key in sorted(kept.keys() - shown.keys(), key=str)] + [
        f"shown, though the case does not name it: {shown[key]}" for key in sorted(shown.keys() - kept.keys(), key=str)
    ]


def drifted(case: ExerciseCase, trace: Trace) -> str | None:
    now, then = set(trace.reached), set(case.reached.items)
    if now == then:
        return None
    against = (
        "the same specification"
        if trace.spec_digest == case.reached.spec_digest
        else f"specification {trace.spec_digest}, recorded against {case.reached.spec_digest}"
    )
    return f"{case.digest} reaches otherwise against {against}: gained {sorted(now - then)}, lost {sorted(then - now)}"


def unmeasured(case: ExerciseCase) -> str | None:
    if case.coverage is None:
        return f"{case.digest} has no coverage measured yet"
    if changed := case.coverage.stale():
        return f"{case.digest}'s coverage, measured at {case.coverage.commit}, is stale: {', '.join(changed)} changed"
    return None


def searched(search: SearchName, run: str, kept_for: KeptFor) -> Searched:
    commit, dirty = checked_out()
    return Searched(search=search, run=run, commit=commit, dirty=dirty, kept_for=kept_for)


class CampaignSettings(_Model):
    examples: int
    steps: int
    keep: int
    least: int
    hours: float | None
    workers: int


class KeptCase(_Model):
    case: str
    kept_for: KeptFor
    steps: int
    worker: int


class Campaign(_Model):
    run: str
    search: SearchName
    settings: CampaignSettings
    commit: str
    dirty: bool
    machine: str | None
    started: datetime
    ended: datetime | None = None
    rounds: int = 0
    rounds_found: int = 0
    unconfirmed: int = 0
    kept: tuple[KeptCase, ...] = ()
    exit: int | None = None


def write_campaign(campaign: Campaign, directory: Path = CASES) -> Path:
    path = directory / CAMPAIGNS / f"{campaign.run}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(campaign.model_dump_json(indent=2) + "\n")
    return path


def campaigns(directory: Path = CASES) -> tuple[Campaign, ...]:
    found = [Campaign.model_validate_json(path.read_text()) for path in (directory / CAMPAIGNS).glob("*.json")]
    return tuple(sorted(found, key=lambda campaign: campaign.started, reverse=True))
