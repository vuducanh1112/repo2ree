"""An exercise case: an exercise kept in the repository's ``exercises/``, with what it must show when replayed, where
it came from, what of the specification it reached, and the code it covered.

A case expects its exercise to conform, or to show exactly the problems it names. A case of the second kind is a
known violation: the searches pass over its problems, and replay holds it to them until a fix makes it conform. Then
it is stale, and its expectation changes to conforming in a commit of its own, as ``exercises/`` is a protected zone:
an expectation excuses what it names, as an expected verdict does.

What a case reached is stamped with the specification it was judged against. The code it covered is stamped with the
commit it was measured at and each covered file's Git blob as it ran: the coverage is stale once any of those files
differs, and is measured again (``python -m repo2ree_testbed exercise-coverage``). It is one field of the case, kept in
a file of its own, ``exercises/coverage/<digest>.json``, outside the protected zone: it changes with the code, and
excuses nothing.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_verdict import (
    Arcs,
    Problem,
    Trace,
    arc_count,
    arcs_union,
    arcs_without,
    digest,
    judge,
    keep,
)

CASES: Final = ROOT / "exercises"
COVERAGE: Final = "coverage"

SearchName = Literal["spec-cov", "branch-cov"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _git(*words: str) -> str:
    return subprocess.run(["git", *words], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def checked_out() -> tuple[str, bool]:
    """The commit checked out, and whether the tree differs from it."""
    return _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain"))


def blobs(paths: Sequence[str]) -> dict[str, str | None]:
    """Each path's Git blob as the file stands now, from the repo root; None for a path no file holds."""
    present = [path for path in paths if (ROOT / path).is_file()]
    hashed = _git("hash-object", "--", *present).splitlines() if present else []
    return {path: dict(zip(present, hashed, strict=True)).get(path) for path in paths}


# ---- Where a case came from, and what it expects ----------------------------------------------------------------


class HandWritten(_Model):
    kind: Literal["hand_written"] = "hand_written"


class ShowedProblems(_Model):
    kind: Literal["showed_problems"] = "showed_problems"


class NewArcs(_Model):
    """It executed arcs no case covered when it was kept: how many, in each file."""

    kind: Literal["new_arcs"] = "new_arcs"
    files: dict[str, int]


type KeptFor = Annotated[ShowedProblems | NewArcs, Field(discriminator="kind")]


class Searched(_Model):
    """Kept by a search, in one of its runs, at a commit (``dirty`` when the tree differed from it), and why."""

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
    """The problems it must show, compared by their kind, step, rule and subject; no more and no fewer."""

    kind: Literal["shows"] = "shows"
    problems: tuple[Problem, ...] = Field(min_length=1)


type Expectation = Annotated[Conforms | Shows, Field(discriminator="kind")]


class Reached(_Model):
    """The rules that triggered and the transitions taken, as the specification ``spec_digest`` names them."""

    spec_digest: str
    items: tuple[str, ...]


# ---- The code a case covered -----------------------------------------------------------------------------------


class CoveredFile(_Model):
    """One file as it was measured: its Git blob then, and the arcs executed in it, as coverage.py numbers them."""

    blob: str
    arcs: tuple[tuple[int, int], ...]


class CaseCoverage(_Model):
    """The code a case covered when ree ran measured, at ``commit`` (``dirty`` when the tree differed from it)."""

    commit: str
    dirty: bool
    files: dict[str, CoveredFile]

    @property
    def arcs(self) -> Arcs:
        return {path: covered.arcs for path, covered in self.files.items()}

    def stale(self) -> tuple[str, ...]:
        """The covered files that differ now from how they ran, or are gone: none, while the coverage holds."""
        now = blobs(tuple(self.files))
        return tuple(path for path, covered in self.files.items() if now[path] != covered.blob)


def coverage_of(arcs: Arcs) -> CaseCoverage:
    """``arcs`` as just measured, stamped with the commit checked out and each file's blob now."""
    commit, dirty = checked_out()
    held = blobs(tuple(arcs))
    files = {path: CoveredFile(blob=blob, arcs=pairs) for path, pairs in arcs.items() if (blob := held[path])}
    return CaseCoverage(commit=commit, dirty=dirty, files=files)


# ---- The case --------------------------------------------------------------------------------------------------


class ExerciseCase(_Model):
    exercise: Exercise
    origin: Origin
    expects: Expectation
    reached: Reached
    # Kept apart, in ``coverage/<digest>.json``; None until it is measured.
    coverage: CaseCoverage | None = Field(default=None, exclude=True)

    @property
    def digest(self) -> str:
        return digest(self.exercise)


def case_of(trace: Trace, origin: Origin, coverage: CaseCoverage | None = None) -> ExerciseCase:
    """The case ``trace`` makes: expecting what it showed, and stamped with what it reached."""
    expects: Expectation = Shows(problems=trace.problems) if trace.problems else Conforms()
    reached = Reached(spec_digest=trace.spec_digest, items=trace.reached)
    return ExerciseCase(exercise=trace.exercise, origin=origin, expects=expects, reached=reached, coverage=coverage)


def write(case: ExerciseCase, directory: Path = CASES) -> Path:
    """Keep ``case`` in ``directory``, named by its exercise, and its coverage, when measured, in ``coverage/``."""
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
    """The cases in ``directory``, each with its coverage when one was measured."""
    found = []
    for path in sorted(directory.glob("*.json")):
        case = ExerciseCase.model_validate_json(path.read_text())
        measured = directory / COVERAGE / path.name
        if measured.is_file():
            case = case.model_copy(update={"coverage": CaseCoverage.model_validate_json(measured.read_text())})
        found.append(case)
    return tuple(found)


def measure(case: ExerciseCase, workdir: Path, directory: Path = CASES) -> tuple[ExerciseCase, list[str]]:
    """Replay ``case`` measured in ``workdir``, keep its trace there, and its coverage in ``directory``: the case with
    it, and how the replay differed from what the case expects, which the coverage of such a run still records."""
    trace = judge(case.exercise, workdir, measured=True)
    keep(workdir, trace)
    measured = case.model_copy(update={"coverage": coverage_of(trace.arcs or {})})
    if measured.coverage is not None:
        write_coverage(case.digest, measured.coverage, directory)
    return measured, unmet(case, trace)


def known(directory: Path = CASES) -> frozenset[tuple[str, str, str]]:
    """The problems the cases name, as another exercise would show them: what the searches pass over."""
    return frozenset(
        problem.known_as
        for case in cases(directory)
        if isinstance(case.expects, Shows)
        for problem in case.expects.problems
    )


def covered(found: Sequence[ExerciseCase]) -> Arcs:
    """The arcs the cases covered together, as their coverage records them."""
    together: Arcs = {}
    for case in found:
        if case.coverage is not None:
            together = arcs_union(together, case.coverage.arcs)
    return together


def adding(candidates: Sequence[Trace], baseline: Arcs, most: int) -> list[tuple[Trace, Arcs]]:
    """At most ``most`` of ``candidates``, each with the arcs it adds: the one adding the most beyond ``baseline``
    first, then the one adding the most beyond that and the first, and so on, while one adds any."""
    chosen: list[tuple[Trace, Arcs]] = []
    so_far = baseline
    for _ in range(most):
        gains = [(trace, arcs_without(trace.arcs or {}, so_far)) for trace in candidates]
        best = max(gains, key=lambda gain: arc_count(gain[1]), default=None)
        if best is None or not arc_count(best[1]):
            break
        chosen.append(best)
        so_far = arcs_union(so_far, best[1])
    return chosen


# ---- Holding a replay to a case --------------------------------------------------------------------------------


def unmet(case: ExerciseCase, trace: Trace) -> list[str]:
    """How ``trace`` differs from what ``case`` expects: nothing when it shows what the case says."""
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
    """How what ``trace`` reached differs from what ``case`` recorded, if it does: worth knowing, never a failure,
    as a specification or a fix may change what an exercise reaches."""
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
    """Why ``case``'s coverage does not hold for the code as it stands, if it does not."""
    if case.coverage is None:
        return f"{case.digest} has no coverage measured yet"
    if changed := case.coverage.stale():
        return f"{case.digest}'s coverage, measured at {case.coverage.commit}, is stale: {', '.join(changed)} changed"
    return None


def searched(search: SearchName, run: str, kept_for: KeptFor) -> Searched:
    """The origin of a case a search keeps now."""
    commit, dirty = checked_out()
    return Searched(search=search, run=run, commit=commit, dirty=dirty, kept_for=kept_for)
