from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import time
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, JsonValue

from repo2ree_ree.reserved_paths import WORKSPACE_CONTROL_PREFIXES
from repo2ree_testbed.api_models import ScriptTarget
from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.cli_machine import Machine
from repo2ree_testbed.environment_journal import EnvironmentJournal
from repo2ree_testbed.exercise import (
    AcquireSource,
    ActivateExperimentEnvironment,
    BuildExperimentEnvironment,
    CheckWorkingEnvironment,
    CrossCheckSbom,
    Drift,
    EvaluateReproducibility,
    Exercise,
    Fetched,
    FileChange,
    FileDrift,
    FilePart,
    GenerateSbom,
    HistoryChange,
    HistoryDrift,
    InitializeRee,
    Label,
    LintScripts,
    LoadReeBundle,
    MaterializeWorkspace,
    ObserveHardware,
    PatchReeDefinition,
    ReflogDrift,
    RemoveSource,
    RevertedDrift,
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
from repo2ree_testbed.exercise_bundle import corrupted
from repo2ree_testbed.exercise_signing import review_bundle, seal_bundle
from repo2ree_testbed.showcases import ALL_PROJECTS, Project, ProjectName

STEP_SECONDS: Final = 900
LOG_LINES: Final = 30
PROJECTS: Final[dict[ProjectName, Project]] = {project.name: project for project in ALL_PROJECTS}


class UnreplayableError(ValueError):
    pass


class Answer(NamedTuple):
    exit: int
    stdout: bytes
    stderr: str


type RunRee = Callable[[Path, Sequence[str], bytes | None], Answer]


def local_ree(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
    done = subprocess.run(
        ["ree", "-C", str(root), *words], input=stdin or b"", capture_output=True, timeout=STEP_SECONDS, check=False
    )
    return Answer(done.returncode, done.stdout, done.stderr.decode(errors="replace"))


def machine_ree(machine: Machine) -> RunRee:
    def run(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        done = machine.ree(root, *words, stdin=stdin, inside=False)
        return Answer(done.status, done.stdout, done.stderr)

    return run


def covered_ree(data: Path) -> RunRee:
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
    words: tuple[str, ...]
    exit: int
    result: JsonValue = None
    log: tuple[str, ...] = ()
    started: float | None = None
    finished: float | None = None


class Prepared(NamedTuple):
    ran: tuple[Ran, ...] = ()
    staged: Path | None = None
    made: bool = True


class Replayed(_Record):
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


def bundle_heads(archive: bytes) -> list[str] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            export = json.loads(bundle.read("export.json"))
        heads = [scope["head"] for scope in export["scopes"]]
    except (zipfile.BadZipFile, KeyError, TypeError, ValueError):
        return None
    return heads if all(isinstance(head, str) for head in heads) else None


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
    run: RunRee
    workdir: Path

    def root(self, label: Label) -> Path:
        return self.workdir / "rees" / label

    @property
    def journals(self) -> Path:
        return self.workdir / "journal"

    def _ran(self, label: Label, words: Sequence[str], stdin: bytes | None = None, plumbing: Sequence[str] = ()) -> Ran:
        started = time.time()
        answer = self.run(self.root(label), ("--json", *plumbing, *words), stdin)
        finished = time.time()
        log = tuple(answer.stderr.splitlines()[-LOG_LINES:])
        said = tuple(word.replace(f"{self.workdir}/", "") for word in words)
        return Ran(
            words=said, exit=answer.exit, result=_result(answer.stdout), log=log, started=started, finished=finished
        )

    def _command(self, journal: EnvironmentJournal, label: Label, command: Command) -> Ran:
        attempt_id = uuid4().hex
        run_id = f"exercise-{attempt_id[:12]}"
        cited = journal.command(attempt_id, label, run_id)
        context = {"operation_id": uuid4().hex, "attempt_id": attempt_id, "dispatch_record": cited}
        plumbing = ("--run-id", run_id, "--context", json.dumps(context))
        ran = self._ran(label, command.words, command.stdin, plumbing)
        history = ran.result.get("history") if isinstance(ran.result, dict) else None
        commit = history.get("after_snapshot_id") if isinstance(history, dict) else None
        record = history.get("record_digest") if isinstance(history, dict) else None
        journal.exited(
            attempt_id,
            label,
            ran.exit,
            commit if isinstance(commit, str) else None,
            record if isinstance(record, str) else None,
        )
        return ran

    def _scope(self, drift: Drift) -> Path:
        return self.root(drift.ree) / "reviews" / drift.review if drift.review else self.root(drift.ree)

    def _undo(
        self, journal: EnvironmentJournal, drifts: list[tuple[int, Drift]], moved: dict[int, str], index: int
    ) -> None:
        for number, drift in drifts:
            if isinstance(drift, HistoryDrift) and drift.until == index and number in moved:
                _git(self._scope(drift), "update-ref", HISTORY_REF, moved.pop(number))
                journal.undone(f"drift-{number}", drift.ree)

    def _drift(self, journal: EnvironmentJournal, number: int, drift: Drift, moved: dict[int, str]) -> None:
        scope = self._scope(drift)
        prefix = f"reviews/{drift.review}/" if drift.review else ""
        if isinstance(drift, ReflogDrift):
            _git(scope, "reflog", "expire", "--expire=now", "--expire-unreachable=now", "--all")
            return
        if isinstance(drift, HistoryDrift):
            left = _git(scope, "rev-parse", "--verify", "--quiet", HISTORY_REF).stdout.strip()
            changed = _rewrite(scope, drift.change, number)
            if changed is not None:
                moved[number] = left
                journal.drifted(f"drift-{number}", drift.ree, f"{prefix}{changed}")
            return
        target = _drifted_file(scope, drift, number)
        if target is None:
            return
        kept = (target.read_bytes(), target.stat().st_mode) if target.is_file() else None
        _change(target, drift.change, number)
        journal.drifted(f"drift-{number}", drift.ree, f"{prefix}{target.relative_to(scope).as_posix()}")
        if isinstance(drift, RevertedDrift):
            _put_back(target, kept)
            journal.undone(f"drift-{number}", drift.ree)

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

    def _prepare(self, journal: EnvironmentJournal, index: int, step: Step) -> Prepared:
        match step:
            case AcquireSource(source=Uploaded(project=project)):
                fixture = PROJECTS[project]
                return Prepared(staged=self._staged(index, fixture.upload_name, fixture.archive()))
            case LoadReeBundle(exported_by=exporter, corruption=corruption):
                bundle_id = f"bundle-{index}"
                journal.bundle(bundle_id, exporter)
                answer = self.run(self.root(exporter), ("bundle",), None)
                exported = Ran(words=("bundle",), exit=answer.exit, log=tuple(answer.stderr.splitlines()[-LOG_LINES:]))
                if answer.exit != 0:
                    journal.refused(bundle_id, exporter, answer.exit)
                    return Prepared((exported,), made=False)
                journal.exported(bundle_id, exporter, bundle_heads(answer.stdout))
                return Prepared(
                    (exported,), self._staged(index, "ree.zip", corrupted(answer.stdout, corruption, index))
                )
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
        journal = EnvironmentJournal(self.journals)
        drifts = list(enumerate(exercise.drifts))
        moved: dict[int, str] = {}
        replayed: list[Replayed] = []
        for index, step in enumerate(exercise.steps):
            self._undo(journal, drifts, moved, index)
            for number, drift in drifts:
                if drift.before == index:
                    self._drift(journal, number, drift, moved)
            prepared = self._prepare(journal, index, step)
            ran = None
            if prepared.made:
                ran = self._command(journal, step.ree, command_of(step, prepared.staged))
            replayed.append(
                Replayed(step=index, ree=step.ree, operation=step.operation, prepared=prepared.ran, ran=ran)
            )
        for number, drift in drifts:
            if drift.before == len(exercise.steps):
                self._drift(journal, number, drift, moved)
        self._undo(journal, drifts, moved, len(exercise.steps))
        journal.close()
        return tuple(replayed)

    def histories(self, exercise: Exercise) -> tuple[Path, ...]:
        return tuple(root for label in exercise.rees if ((root := self.root(label)) / ".git").is_dir())


DRIFTED: Final = "changed outside ree"
GIT_IDENTITY: Final = ("-c", "user.name=environment", "-c", "user.email=environment@repo2ree.invalid")
HISTORY_REF: Final = "refs/heads/ree-history"


def _git(scope: Path, *words: str, index: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "GIT_INDEX_FILE": str(index)} if index is not None else None
    return subprocess.run(
        ["git", "--git-dir", str(scope / ".git"), "--work-tree", str(scope), *GIT_IDENTITY, *words],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def _files(scope: Path, part: FilePart) -> list[Path]:
    if part == "records":
        listed = _git(scope, "ls-tree", "-r", "--name-only", HISTORY_REF)
        names = [name for name in listed.stdout.splitlines() if not name.startswith(f"{part_dir('overlay')}/")]
        return [scope / name for name in sorted(names) if (scope / name).is_file()]
    base = scope / part_dir(part)
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and not path.is_symlink() and not path.name.startswith(WORKSPACE_CONTROL_PREFIXES)
    )


def part_dir(part: FilePart) -> str:
    return {"overlay": "overlay", "records": "."}[part]


def _drifted_file(scope: Path, drift: FileDrift | RevertedDrift, number: int) -> Path | None:
    if drift.change == "add":
        base = scope / part_dir(drift.part)
        return base / f"drift-{number}.txt" if base.is_dir() else None
    files = _files(scope, drift.part)
    return files[drift.pick % len(files)] if files else None


def _change(target: Path, change: FileChange, number: int) -> None:
    match change:
        case "add" | "write":
            target.write_text(f"{DRIFTED} {number}\n", encoding="utf-8")
        case "append":
            with target.open("a", encoding="utf-8") as stream:
                stream.write(f"\n{DRIFTED} {number}\n")
        case "remove":
            target.unlink()
        case "mode":
            target.chmod(target.stat().st_mode ^ stat.S_IXUSR)


def _put_back(target: Path, kept: tuple[bytes, int] | None) -> None:
    if kept is None:
        target.unlink(missing_ok=True)
        return
    content, mode = kept
    target.write_bytes(content)
    target.chmod(stat.S_IMODE(mode))


def _rewrite(scope: Path, change: HistoryChange, number: int) -> str | None:
    head = _git(scope, "rev-parse", "--verify", "--quiet", HISTORY_REF).stdout.strip()
    if not head:
        return None
    match change:
        case "commit":
            words = [("add", "-A"), ("commit", "--quiet", "--allow-empty", "-m", f"{DRIFTED} {number}")]
        case "reset":
            words = [("reset", "--quiet", "--soft", "HEAD^")]
        case "amend":
            words = [("add", "-A"), ("commit", "--quiet", "--allow-empty", "--amend", "--no-edit")]
    if any(_git(scope, *command).returncode for command in words):
        return None
    if _git(scope, "rev-parse", "--verify", "--quiet", HISTORY_REF).stdout.strip() == head:
        return None
    return f".git/{HISTORY_REF}"
