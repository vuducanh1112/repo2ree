from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal

from coverage import Coverage
from coverage.exceptions import NoDataError
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_cli import CliReplay, Ran, Replayed, RunRee, covered_ree, local_ree

CLI_SCHEMA: Final = ROOT / "contracts/cli/cli.schema.json"

ProblemKind = Literal["answer", "violated"]
AnswerRule = Literal["exit_status", "no_result", "result_shape", "outputs_shape"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Problem(_Model):
    kind: ProblemKind
    step: int | None = None
    rule: str
    subject: str
    detail: str = ""

    @property
    def key(self) -> tuple[ProblemKind, int | None, str, str]:
        return self.kind, self.step, self.rule, self.subject

    @property
    def known_as(self) -> tuple[ProblemKind, str, str]:
        return self.kind, self.rule, self.subject

    def __str__(self) -> str:
        where = f"step {self.step}: " if self.step is not None else ""
        return f"{where}{self.rule} {self.subject}: {self.detail}"


class Judged(_Model):
    problems: tuple[Problem, ...]
    reached: tuple[str, ...]
    spec_digest: str


type Arcs = dict[str, tuple[tuple[int, int], ...]]


def arc_count(arcs: Arcs) -> int:
    return sum(map(len, arcs.values()))


def arcs_without(arcs: Arcs, known: Arcs) -> Arcs:
    left: Arcs = {}
    for path, pairs in arcs.items():
        seen = set(known.get(path, ()))
        if fresh := tuple(arc for arc in pairs if arc not in seen):
            left[path] = fresh
    return left


def arcs_union(arcs: Arcs, more: Arcs) -> Arcs:
    return {path: tuple(sorted({*arcs.get(path, ()), *more.get(path, ())})) for path in sorted({*arcs, *more})}


class Trace(_Model):
    exercise: Exercise
    replayed: tuple[Replayed, ...]
    problems: tuple[Problem, ...]
    reached: tuple[str, ...]
    spec_digest: str
    arcs: Arcs | None = None

    @property
    def digest(self) -> str:
        return digest(self.exercise)

    @property
    def arc_count(self) -> int:
        return arc_count(self.arcs or {})


class Covered(_Model):
    digest: str
    steps: int
    problems: int
    reached: tuple[str, ...]
    new_reached: tuple[str, ...]
    arcs: int | None = None
    new_arcs: Arcs | None = None


class SoFar(_Model):
    exercises: int = 0
    reached: tuple[str, ...] = ()
    arcs: Arcs = {}


@cache
def cli_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(CLI_SCHEMA.read_text())
    return schema


def schema_command(words: Sequence[str]) -> dict[str, Any]:
    commands = sorted(cli_schema()["commands"], key=lambda command: -len(command["words"]))
    return next(command for command in commands if tuple(words[: len(command["words"])]) == tuple(command["words"]))


def _validator(reference: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator({**reference, "$defs": cli_schema()["$defs"]})


def _answer_problems(step: int, ran: Ran) -> list[Problem]:
    command = schema_command(ran.words)
    subject = "ree " + " ".join(command["words"])

    def problem(rule: AnswerRule, detail: str) -> Problem:
        return Problem(kind="answer", step=step, rule=rule, subject=subject, detail=detail)

    if str(ran.exit) not in cli_schema()["exit_codes"]:
        return [problem("exit_status", f"exited {ran.exit}, which ree schema declares no exit status for")]
    if command["stdout"] != "result":
        return []
    if not isinstance(ran.result, dict):
        return [problem("no_result", f"exited {ran.exit} and printed no result")]
    problems = [
        problem("result_shape", error.message) for error in _validator(cli_schema()["result"]).iter_errors(ran.result)
    ]
    if ran.result.get("status") == "succeeded" and command.get("outputs"):
        outputs = ran.result.get("outputs")
        problems += [
            problem("outputs_shape", error.message) for error in _validator(command["outputs"]).iter_errors(outputs)
        ]
    return problems


def answer_problems(replayed: Sequence[Replayed]) -> list[Problem]:
    return [
        problem
        for step in replayed
        for ran in (*step.prepared, *((step.ran,) if step.ran else ()))
        for problem in _answer_problems(step.step, ran)
    ]


def behaviour(histories: Sequence[Path], output: Path, journals: Path | None = None) -> Judged:
    gits = [word for history in histories for word in ("--git", str(history))]
    journaled = ["--journal", str(journals)] if journals is not None and journals.is_dir() else []
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "check", *gits, *journaled, "-o", str(output)]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    report = output / "assurance.json"
    if not report.is_file():
        raise RuntimeError(f"the checker wrote no report (exit {done.returncode}):\n{done.stderr}")
    result = json.loads(report.read_text())
    violated = [
        Problem(kind="violated", rule=rule["rule"], subject=finding["subject"], detail=finding["reason"])
        for rule in result["rules"]
        for finding in rule["findings"]
        if finding["verdict"] == "violated"
    ]
    rules = [rule["rule"] for rule in result["rules"] if rule["triggered"]]
    edges = [
        f"{entity} {edge}"
        for entity, counts in result["coverage"]["transitions"].items()
        for edge, count in counts.items()
        if count
    ]
    return Judged(problems=tuple(violated), reached=tuple(sorted([*rules, *edges])), spec_digest=result["spec_digest"])


def digest(exercise: Exercise) -> str:
    return hashlib.sha256(exercise.model_dump_json().encode()).hexdigest()[:16]


def arcs_executed(data: Path) -> Arcs:
    measured = Coverage(data_file=str(data / ".coverage"), config_file=str(ROOT / "pyproject.toml"))
    try:
        measured.combine([str(data)])
    except NoDataError:
        return {}
    measured.save()
    combined = measured.get_data()
    return {
        str(Path(path).relative_to(ROOT)) if Path(path).is_relative_to(ROOT) else path: tuple(sorted(arcs))
        for path in sorted(combined.measured_files())
        if (arcs := combined.arcs(path))
    }


def judge(exercise: Exercise, workdir: Path, *, measured: bool = False, run: RunRee = local_ree) -> Trace:
    data = workdir / "coverage"
    replay = CliReplay(covered_ree(data) if measured else run, workdir)
    replayed = replay.replay(exercise)
    checked = behaviour(replay.histories(exercise), workdir / "check", replay.journals)
    problems = (*answer_problems(replayed), *checked.problems)
    arcs = arcs_executed(data) if measured else None
    return Trace(
        exercise=exercise,
        replayed=replayed,
        problems=problems,
        reached=checked.reached,
        spec_digest=checked.spec_digest,
        arcs=arcs,
    )


def keep(workdir: Path, trace: Trace) -> None:
    (workdir / "trace.json").write_text(trace.model_dump_json(indent=2) + "\n")
    so_far_file = workdir.parent / "covered.json"
    so_far = SoFar.model_validate_json(so_far_file.read_text()) if so_far_file.is_file() else SoFar()
    arcs = trace.arcs or {}
    covered = Covered(
        digest=trace.digest,
        steps=len(trace.exercise.steps),
        problems=len(trace.problems),
        reached=trace.reached,
        new_reached=tuple(item for item in trace.reached if item not in set(so_far.reached)),
        arcs=trace.arc_count if trace.arcs is not None else None,
        new_arcs=arcs_without(arcs, so_far.arcs) if trace.arcs is not None else None,
    )
    with (workdir.parent / "coverage.ndjson").open("a") as index:
        index.write(covered.model_dump_json() + "\n")
    together = SoFar(
        exercises=so_far.exercises + 1,
        reached=tuple(sorted({*so_far.reached, *trace.reached})),
        arcs=arcs_union(so_far.arcs, arcs),
    )
    so_far_file.write_text(together.model_dump_json() + "\n")
    if not trace.problems:
        for heavy in ("rees", "staged"):
            shutil.rmtree(workdir / heavy, ignore_errors=True)
