"""An exercise replayed through ``ree``: each step is one command against the directory its REE's label names.

What a step takes is made before its command runs: a project's source packed as an upload, another REE's export
(``ree bundle``) as it stands at that step, a signature over the seal or the review record as ``ree`` shows it at
that step. When what a step takes cannot be made, because the REE it exports does not answer, the step runs no
command. Replay judges nothing: what each command answered is kept as it answered.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import BaseModel, ConfigDict, JsonValue

from repo2ree_testbed.api_models import ScriptTarget
from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.cli_machine import Machine
from repo2ree_testbed.exercise import (
    AcquireSource,
    ActivateExperimentEnvironment,
    BuildExperimentEnvironment,
    CheckWorkingEnvironment,
    CrossCheckSbom,
    EvaluateReproducibility,
    Exercise,
    Fetched,
    GenerateSbom,
    InitializeRee,
    Label,
    LintScripts,
    LoadReeBundle,
    MaterializeWorkspace,
    ObserveHardware,
    PatchReeDefinition,
    RemoveSource,
    ReviewAcquireSource,
    ReviewActivateExperimentEnvironment,
    ReviewBuildExperimentEnvironment,
    ReviewRunExperiment,
    RunExperiment,
    SealRee,
    SignRee,
    SignReview,
    Step,
    SuggestScripts,
    Text,
    Uploaded,
    WriteScript,
)
from repo2ree_testbed.exercise_signing import review_bundle, seal_bundle
from repo2ree_testbed.showcases import ALL_PROJECTS, Project, ProjectName

# Long enough for a build that installs offline: a step waits for its command, as a person does.
STEP_SECONDS: Final = 900
LOG_LINES: Final = 30
PROJECTS: Final[dict[ProjectName, Project]] = {project.name: project for project in ALL_PROJECTS}


class UnreplayableError(ValueError):
    """The exercise asks for what this replay cannot do yet."""


class Answer(NamedTuple):
    exit: int
    stdout: bytes
    stderr: str


type RunRee = Callable[[Path, Sequence[str], bytes | None], Answer]


def local_ree(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
    """``ree -C root`` on this machine, which then runs the REE's scripts here too."""
    done = subprocess.run(
        ["ree", "-C", str(root), *words], input=stdin or b"", capture_output=True, timeout=STEP_SECONDS, check=False
    )
    return Answer(done.returncode, done.stdout, done.stderr.decode(errors="replace"))


def machine_ree(machine: Machine) -> RunRee:
    """``ree`` on the test's machine, which runs the REE's scripts there: its REEs must be in the directory the
    machine shares with this process."""

    def run(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        done = machine.ree(root, *words, stdin=stdin)
        return Answer(done.status, done.stdout, done.stderr)

    return run


def covered_ree(data: Path) -> RunRee:
    """``ree`` as ``local_ree`` runs it, measured by coverage.py under the repo's configuration (branches on): each
    command writes the arcs it executed to a data file of its own in ``data``."""
    data.mkdir(parents=True, exist_ok=True)
    measured = [sys.executable, "-m", "coverage", "run", "--parallel-mode", f"--rcfile={ROOT / 'pyproject.toml'}"]
    variables = {**os.environ, "COVERAGE_FILE": str(data / ".coverage")}

    def run(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        done = subprocess.run(
            [*measured, "-m", "repo2ree_cli", "-C", str(root), *words],
            input=stdin or b"",
            capture_output=True,
            timeout=STEP_SECONDS,
            check=False,
            cwd=ROOT,
            env=variables,
        )
        return Answer(done.returncode, done.stdout, done.stderr.decode(errors="replace"))

    return run


class Command(NamedTuple):
    words: tuple[str, ...]
    stdin: bytes | None = None


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Ran(_Record):
    """One ``ree`` command: its words, its exit status, the one result line ``--json`` printed, if it printed one,
    and the end of its log."""

    words: tuple[str, ...]
    exit: int
    result: JsonValue = None
    log: tuple[str, ...] = ()


class Prepared(NamedTuple):
    ran: tuple[Ran, ...] = ()
    staged: Path | None = None
    made: bool = True


class Replayed(_Record):
    """One step: what replay ran to make what it takes, and its command, unless that could not be made."""

    step: int
    ree: Label
    operation: str
    prepared: tuple[Ran, ...] = ()
    ran: Ran | None


def _target(target: ScriptTarget) -> str:
    return f"{target.kind}:{target.experiment_name}" if target.experiment_name else target.kind


def _targets(targets: Sequence[ScriptTarget]) -> tuple[str, ...]:
    return tuple(word for target in targets for word in ("--target", _target(target)))


def _switch(name: str, on: bool) -> str:
    return f"--{name}" if on else f"--no-{name}"


def command_of(step: Step, staged: Path | None = None) -> Command:
    """The words of the command that runs ``step``, and what it reads on stdin. ``staged`` is the file a step that
    takes one takes: an upload, a bundle to load, or a signature."""
    match step:
        case InitializeRee(name=name):
            return Command(("initialize-ree", "--name", name or step.ree))
        case AcquireSource(source=Uploaded()):
            return Command(("acquire-source", "--archive", str(staged)))
        case AcquireSource(source=Fetched(origin_url=url, source_type=kind, revision=revision)):
            pinned = ("--revision", revision) if revision else ()
            return Command(("acquire-source", "--origin-url", url, "--source-type", kind, *pinned))
        case RemoveSource():
            return Command(("remove-source",))
        case LoadReeBundle():
            return Command(("load-ree-bundle", "--archive", str(staged)))
        case PatchReeDefinition(patch=patch):
            return Command(("patch-ree-definition",), patch.model_dump_json(exclude_none=True).encode())
        case WriteScript(script=script, experiment=experiment, content=content):
            target = f"{script}:{experiment}" if experiment else script
            text = content.text if isinstance(content, Text) else PROJECTS[content.project].recipe(content.file)
            return Command(("write-script", target), text.encode())
        case SuggestScripts(targets=targets):
            return Command(("suggest-scripts", *_targets(targets)))
        case LintScripts(targets=targets):
            return Command(("lint-scripts", *_targets(targets)))
        case EvaluateReproducibility(strict=strict):
            return Command(("evaluate-reproducibility", _switch("strict", strict)))
        case (
            ObserveHardware()
            | CheckWorkingEnvironment()
            | MaterializeWorkspace()
            | BuildExperimentEnvironment()
            | GenerateSbom()
            | CrossCheckSbom()
            | ActivateExperimentEnvironment()
        ):
            return Command((step.operation.replace("_", "-"),))
        case RunExperiment(experiment=experiment):
            return Command(("run-experiment", experiment))
        case SealRee():
            return Command(
                (
                    "seal-ree",
                    _switch("source-included", step.source_included),
                    _switch("experiment-environment-included", step.experiment_environment_included),
                    _switch("results-included", step.results_included),
                )
            )
        case SignRee(claim=claim):
            return Command(("sign-ree", "--claim", claim, "--bundle", str(staged)))
        case ReviewAcquireSource(review=review, basis=basis):
            return Command(("review", "acquire-source", "--review-id", review, "--basis", basis))
        case ReviewBuildExperimentEnvironment(review=review, basis=basis):
            return Command(("review", "build-experiment-environment", "--review-id", review, "--basis", basis))
        case ReviewActivateExperimentEnvironment(review=review):
            return Command(("review", "activate-experiment-environment", "--review-id", review))
        case ReviewRunExperiment(review=review, experiment=experiment):
            return Command(("review", "run-experiment", "--review-id", review, experiment))
        case SignReview(review=review):
            return Command(("sign-review", "--review-id", review, "--bundle", str(staged)))
    raise AssertionError(f"no command for {step.operation}")


def _result(stdout: bytes) -> JsonValue:
    lines = stdout.decode(errors="replace").strip().splitlines()
    try:
        return json.loads(lines[-1]) if lines else None
    except ValueError:
        return None


def _outputs(ran: Ran) -> dict[str, JsonValue]:
    if isinstance(ran.result, dict) and ran.result.get("status") == "succeeded":
        outputs = ran.result.get("outputs")
        return outputs if isinstance(outputs, dict) else {}
    return {}


@dataclass
class CliReplay:
    """Replays exercises through ``run``, each REE in ``workdir/rees/<label>``."""

    run: RunRee
    workdir: Path

    def root(self, label: Label) -> Path:
        return self.workdir / "rees" / label

    def _ran(self, label: Label, words: Sequence[str], stdin: bytes | None = None) -> Ran:
        answer = self.run(self.root(label), ("--json", *words), stdin)
        log = tuple(answer.stderr.splitlines()[-LOG_LINES:])
        said = tuple(word.replace(f"{self.workdir}/", "") for word in words)
        return Ran(words=said, exit=answer.exit, result=_result(answer.stdout), log=log)

    def _staged(self, index: int, name: str, content: bytes) -> Path:
        staged = self.workdir / "staged" / str(index) / name
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(content)
        return staged

    def _seal(self, label: Label) -> tuple[Ran, str | None]:
        shown = self._ran(label, ("show", "--summary"))
        ree = _outputs(shown).get("ree")
        seal = ree.get("seal") if isinstance(ree, dict) else None
        digest = seal.get("ree_digest") if isinstance(seal, dict) else None
        return shown, digest if isinstance(digest, str) else None

    def _review_record(self, label: Label, review: Label) -> tuple[Ran, JsonValue]:
        answer = self.run(self.root(label), ("cat", f"reviews/{review}/review.json"), None)
        ran = Ran(words=("cat", f"reviews/{review}/review.json"), exit=answer.exit)
        try:
            return ran, json.loads(answer.stdout) if answer.exit == 0 else {}
        except ValueError:
            return ran, {}

    def _prepare(self, index: int, step: Step) -> Prepared:
        """What replay runs to make the file ``step`` takes, and that file, unless it could not be made."""
        match step:
            case AcquireSource(source=Uploaded(project=project)):
                fixture = PROJECTS[project]
                return Prepared(staged=self._staged(index, fixture.upload_name, fixture.archive()))
            case LoadReeBundle(exported_by=exporter):
                answer = self.run(self.root(exporter), ("bundle",), None)
                exported = Ran(words=("bundle",), exit=answer.exit, log=tuple(answer.stderr.splitlines()[-LOG_LINES:]))
                if answer.exit != 0:
                    return Prepared((exported,), made=False)
                return Prepared((exported,), self._staged(index, "ree.zip", answer.stdout))
            case SignRee(signature=signature):
                shown, seal = self._seal(step.ree)
                return Prepared((shown,), self._staged(index, "seal.sigstore.json", seal_bundle(seal, signature)))
            case SignReview(review=review, signature=signature):
                read, record = self._review_record(step.ree, review)
                subject = record.get("subject") if isinstance(record, dict) else None
                reviewed = subject.get("ree_digest") if isinstance(subject, dict) else None
                bundle = review_bundle(reviewed if isinstance(reviewed, str) else None, record, signature)
                return Prepared((read,), self._staged(index, "review.sigstore.json", bundle))
        return Prepared()

    def replay(self, exercise: Exercise) -> tuple[Replayed, ...]:
        if exercise.faults:
            raise UnreplayableError("the CLI replay lands no faults yet")
        self.root(exercise.rees[0]).parent.mkdir(parents=True, exist_ok=True)
        replayed: list[Replayed] = []
        for index, step in enumerate(exercise.steps):
            prepared = self._prepare(index, step)
            ran = None
            if prepared.made:
                command = command_of(step, prepared.staged)
                ran = self._ran(step.ree, command.words, command.stdin)
            replayed.append(
                Replayed(step=index, ree=step.ree, operation=step.operation, prepared=prepared.ran, ran=ran)
            )
        return tuple(replayed)

    def histories(self, exercise: Exercise) -> tuple[Path, ...]:
        """The REE directories that hold a history once the exercise ran: what the behaviour check reads."""
        return tuple(root for label in exercise.rees if ((root := self.root(label)) / ".git").is_dir())
