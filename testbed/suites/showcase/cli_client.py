"""The showcases' steps through ``ree``, run on the test's machine as the user who logs in to it.

The stack under a CLI showcase starts its store's machine as for any showcase; this client works beside the
workbench there, never through it: each step is a ``ree`` command on that machine, against an REE in a directory
the machine and this process share. What a step printed is its log, and its result is the one line ``--json``
writes. ``ree`` runs an REE's scripts on the machine it runs on.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import time
import warnings
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict, Field
from typed_client import Client, NewRee, Reproduction

from repo2ree_testbed.api_models import (
    AcquirableSourceType,
    Audit,
    Cpu,
    DefinitionPatch,
    HardwarePatch,
    InferenceReport,
    InferenceResult,
    Ree,
    Review,
    ReviewBasis,
    ReviewSet,
    Run,
    RunStatus,
    ScriptKind,
)
from repo2ree_testbed.cli_session import LOG_LINES, CliCommand, append, kept_result, kept_stdin, session_file
from repo2ree_testbed.run_watch import INSTANT_RUN, RunWatch
from repo2ree_testbed.showcases import Project
from repo2ree_testbed.stack.environments import (
    ENVIRONMENTS,
    MACHINE_CONTAINER_VARIABLE,
    MACHINE_VARIABLE,
    MACHINE_WORKDIR_VARIABLE,
    EnvironmentName,
    machine_exec,
)
from repo2ree_testbed.stack.sigstore import local_sigstore

BUILD_SCRIPT = "ree-scripts/build_experiment_environment.sh"
LAUNCH_SCRIPT = "ree-scripts/launch.sh"
# Long enough for a build that pulls and compiles: the command line waits for its step, as a person does.
STEP_SECONDS = 3600


class CliError(AssertionError):
    pass


class Result(BaseModel):
    """The one line ``ree --json`` prints: how the command ended and what it found."""

    model_config = ConfigDict(extra="ignore")

    status: RunStatus
    outputs: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class Done:
    """What one ``ree`` command left: its exit status and what it wrote."""

    status: int
    stdout: bytes
    stderr: str


@dataclass
class Machine:
    """The test's machine, and the directory it shares with this process."""

    environment: EnvironmentName
    container: str
    workdir: Path

    def ree(self, root: Path, *words: str, stdin: bytes | None = None, variables: dict[str, str] | None = None) -> Done:
        command = machine_exec(
            ENVIRONMENTS[self.environment], self.container, ["ree", "-C", str(root), *words], variables
        )
        done = subprocess.run(command, input=stdin or b"", capture_output=True, timeout=STEP_SECONDS, check=False)
        return Done(done.returncode, done.stdout, done.stderr.decode(errors="replace"))


@dataclass
class CliClient:
    """The showcases' steps as ``ree`` commands; an REE is its directory, named by its id."""

    machine: Machine
    archive_dir: Path
    # Where each REE's histories are kept before the REE is removed: the evidence the behaviour check reads, as
    # no control plane serves an REE this client runs ree in.
    kept_dir: Path
    # Where every command the test runs is written down, as it typed it and as ree answered (cli_session).
    session: Path | None = None
    _logs: dict[str, str] = field(default_factory=dict)

    def root(self, ree_id: str) -> Path:
        return self.machine.workdir / ree_id

    # ---- running ree ----------------------------------------------------------

    def _result(
        self, ree_id: str, *words: str, stdin: bytes | None = None, variables: dict[str, str] | None = None
    ) -> tuple[str, Result]:
        """Run one command of the REE's and keep what it logged; its run and its one result line."""
        run_id = f"cli-{uuid4().hex[:12]}"
        done = self._ree(ree_id, ("--json", "--run-id", run_id, *words), stdin, run_id, variables)
        self._logs[run_id] = _lines(done.stderr)
        try:
            return run_id, Result.model_validate_json(done.stdout.decode().strip().splitlines()[-1])
        except (IndexError, ValueError) as exc:
            raise CliError(f"ree {' '.join(words)} wrote no result (exit {done.status}):\n{done.stderr}") from exc

    def _step(
        self, ree_id: str, *words: str, stdin: bytes | None = None, variables: dict[str, str] | None = None
    ) -> Run:
        run_id, result = self._result(ree_id, *words, stdin=stdin, variables=variables)
        return Run(run_id=run_id, status=result.status)

    def _outputs(self, ree_id: str, *words: str, stdin: bytes | None = None) -> dict[str, Any]:
        run_id, result = self._result(ree_id, *words, stdin=stdin)
        if result.status != "succeeded":
            raise CliError(f"ree {' '.join(words)} ended {result.status}\n{self._logs[run_id]}")
        return result.outputs

    def _ree(
        self,
        ree_id: str,
        words: tuple[str, ...],
        stdin: bytes | None = None,
        run_id: str | None = None,
        variables: dict[str, str] | None = None,
    ) -> Done:
        """Run one ``ree`` command against the REE, and add it to the test's session as it was typed and answered."""
        started = time.time()
        done = self.machine.ree(self.root(ree_id), *words, stdin=stdin, variables=variables)
        if self.session is not None:
            printed = done.stdout.decode(errors="replace").strip().splitlines()
            result, result_bytes = kept_result(printed[-1]) if "--json" in words and printed else (None, 0)
            text, stdin_bytes = kept_stdin(stdin)
            command = CliCommand(
                ree=ree_id,
                words=tuple(word for word in words if word != "--json" and word != "--run-id" and word != run_id),
                run_id=run_id,
                stdin=text,
                stdin_bytes=stdin_bytes,
                exit=done.status,
                result=result,
                result_bytes=result_bytes,
                stdout_bytes=0 if result is not None else len(done.stdout),
                log=tuple(_log(done.stderr)[-LOG_LINES:]),
                started=started,
                finished=time.time(),
            )
            append(self.session, command)
        return done

    def _bytes(self, ree_id: str, *words: str) -> bytes:
        done = self._ree(ree_id, words)
        if done.status != 0:
            raise CliError(f"ree {' '.join(words)} exited {done.status}: {done.stderr}")
        return done.stdout

    def _write(self, ree_id: str, path: str, content: str) -> None:
        self._outputs(ree_id, "write-script", path, stdin=content.encode())

    def _write_proposed(self, ree_id: str, target: str, rule: str) -> None:
        self._outputs(ree_id, "suggest-scripts", "--target", target, "--write", "--rule", rule)

    def _staged(self, data: bytes, name: str) -> Path:
        staged = self.machine.workdir / "uploads" / uuid4().hex / name
        staged.parent.mkdir(parents=True)
        staged.write_bytes(data)
        return staged

    def create(self, name: str) -> str:
        """Create an REE, and its kept folder: one with no history in it is an REE whose history went unkept."""
        ree_id = f"{name[:40]}-{uuid4().hex[:8]}"
        (self.kept_dir / ree_id).mkdir(parents=True, exist_ok=True)
        self._outputs(ree_id, "initialize-ree", "--name", name)
        return ree_id

    def _keep(self, ree_id: str) -> None:
        """Copy the REE's histories, its own and each review's, into its kept folder, each under its history lock.

        LFS payloads stay out: the history commits their pointers, which is all the check reads. A copy that fails
        leaves the folder empty, so the REE is listed as unkept rather than as a history cut short.
        """
        root, kept = self.root(ree_id), self.kept_dir / ree_id
        scopes = [root, *sorted(path for path in (root / "reviews").glob("*") if (path / ".git").is_dir())]
        try:
            with ExitStack() as locks:
                for scope in scopes:
                    if (lock := scope / ".git/repo2ree.lock").is_file():
                        fcntl.flock(locks.enter_context(lock.open("rb")), fcntl.LOCK_EX)
                for scope in scopes:
                    target = kept / scope.relative_to(root) / ".git"
                    shutil.copytree(scope / ".git", target, symlinks=True, ignore=_without_lfs, dirs_exist_ok=True)
        except OSError as exc:
            shutil.rmtree(kept, ignore_errors=True)
            kept.mkdir(parents=True, exist_ok=True)
            warnings.warn(f"the history of {ree_id} was not kept: {exc}", stacklevel=2)

    # ---- the Client the showcases use -------------------------------------------

    def logs(self, ree_id: str, run: Run) -> str:
        return self._logs.get(run.run_id, "")

    def ree(self, ree_id: str) -> Ree:
        return Ree.model_validate(self._outputs(ree_id, "show", "--summary")["ree"])

    def audit(self, ree_id: str) -> Audit:
        return Audit.model_validate(self._outputs(ree_id, "show", "--summary")["audit"])

    def exists(self, ree_id: str) -> bool:
        return (self.root(ree_id) / "ree.json").is_file()

    def release(self, ree_id: str) -> None:
        self._keep(ree_id)
        subprocess.run(["rm", "-rf", str(self.root(ree_id))], check=False)

    def upload_source(self, ree_id: str, fixture: Project) -> None:
        archive = self._staged(fixture.archive(), fixture.upload_name)
        self._outputs(ree_id, "acquire-source", "--archive", str(archive))

    def fetch_source(self, ree_id: str, origin_url: str, source_type: AcquirableSourceType) -> Run:
        return self._step(ree_id, "acquire-source", "--origin-url", origin_url, "--source-type", source_type)

    def declare_name(self, ree_id: str, name: str) -> None:
        self._outputs(ree_id, "patch-ree-definition", "--name", name)

    def declare_catalog(self, ree_id: str, *, version: str, description: str) -> None:
        self._outputs(ree_id, "patch-ree-definition", "--version", version, "--description", description)

    def declare_cpu(self, ree_id: str, model: str, cpu: Cpu) -> None:
        patch = DefinitionPatch(hbom=HardwarePatch(cpus={model: cpu})).model_dump(exclude_none=True)
        self._outputs(ree_id, "patch-ree-definition", stdin=json.dumps(patch).encode())

    def declare_experiment(self, ree_id: str, fixture: Project) -> None:
        outputs = [word for path in fixture.outputs for word in ("--output", str(path))]
        self._outputs(ree_id, "patch-ree-definition", "--experiment", fixture.experiment, *outputs)
        self._write(ree_id, fixture.experiment_script, fixture.recipe("experiment.sh"))
        self._write(ree_id, fixture.experiment_verify, fixture.recipe("experiment.verify.sh"))

    def evaluate(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "evaluate-reproducibility")

    def infer(self, ree_id: str, kind: ScriptKind, *, experiment: str | None = None) -> InferenceResult:
        target = f"{kind}:{experiment}" if experiment is not None else kind
        [result] = InferenceReport.model_validate(self._outputs(ree_id, "suggest-scripts", "--target", target)).results
        return result

    def check_working_environment(self, ree_id: str, fixture: Project) -> Run:
        """Write the project's check of what its scripts need, and run it through the launch the project declares."""
        if fixture.launches:
            rule = fixture.rule("launch.sh")
            if rule:
                self._write_proposed(ree_id, "launch", rule)
            else:
                self._write(ree_id, LAUNCH_SCRIPT, fixture.recipe("launch.sh"))
            self._outputs(ree_id, "patch-ree-definition", "--launch")
        self._write(ree_id, fixture.check_script, fixture.recipe("check_working_environment.sh"))
        return self._step(ree_id, "check-working-environment")

    def build_experiment_environment(self, ree_id: str, fixture: Project, script: str | None = None) -> Run:
        """Check the working environment as the project does, declare the experiment environment, ask inference for
        its build, and build with ``script``, else as the project writes it; a project that launches its scripts
        declares its launch before the check. A check that fails is the step's result, and nothing is built."""
        checked = self.check_working_environment(ree_id, fixture)
        if checked.status != "succeeded":
            return checked
        self._outputs(ree_id, "patch-ree-definition", "--artifact-path", fixture.experiment_environment_path)
        self.infer(ree_id, "build_experiment_environment")
        rule = fixture.rule("build_experiment_environment.sh")
        if script is None and rule:
            self._write_proposed(ree_id, "build_experiment_environment", rule)
        else:
            self._write(ree_id, BUILD_SCRIPT, script or fixture.recipe("build_experiment_environment.sh"))
        if fixture.rule("activate_experiment_environment.sh") is None:
            self._write(ree_id, "activate_experiment_environment", fixture.recipe("activate_experiment_environment.sh"))
        return self._step(ree_id, "build-experiment-environment")

    def generate_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "generate-sbom")

    def cross_check_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "cross-check-sbom")

    def activate(self, ree_id: str, fixture: Project) -> Run:
        rule = fixture.rule("activate_experiment_environment.sh")
        if rule:
            self._write_proposed(ree_id, "activate_experiment_environment", rule)
        return self._step(ree_id, "activate-experiment-environment")

    def run_experiment(self, ree_id: str, fixture: Project) -> Run:
        self.declare_experiment(ree_id, fixture)
        self.infer(ree_id, "experiment_run", experiment=fixture.experiment)
        self.infer(ree_id, "experiment_verify", experiment=fixture.experiment)
        return self._step(ree_id, "run-experiment", fixture.experiment)

    def author(self, ree_id: str, fixture: Project) -> None:
        self.upload_source(ree_id, fixture)
        self._outputs(ree_id, "evaluate-reproducibility")
        self._outputs(ree_id, "observe-hardware")
        for label, run in (
            ("build_experiment_environment", lambda: self.build_experiment_environment(ree_id, fixture)),
            ("activation", lambda: self.activate(ree_id, fixture)),
            ("experiment", lambda: self.run_experiment(ree_id, fixture)),
        ):
            done = run()
            assert done.status == "succeeded", f"{label} ended {done.status}\n{self.logs(ree_id, done)}"

    def seal(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "seal-ree")

    def sign(self, ree_id: str) -> Run:
        """Sign the sealed REE with the run's Sigstore, as its author does: signed in by a token in the environment,
        never among the words typed."""
        local = local_sigstore()
        trust = self._staged(local.trust_config.read_bytes(), "trust_config.json")
        token = {"SIGSTORE_IDENTITY_TOKEN": local.token()}
        return self._step(ree_id, "sign-ree", "--trust-config", str(trust), variables=token)

    def archive(self, ree_id: str, label: str) -> Path:
        target = self.archive_dir / f"{label}-{ree_id}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._bytes(ree_id, "bundle"))
        return target

    def load(self, ree_id: str, bundle: bytes) -> None:
        self._outputs(ree_id, "load-ree-bundle", "--archive", str(self._staged(bundle, "ree.zip")))

    def review_acquire_source(self, ree_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "review", "acquire-source", "--basis", basis)

    def reviews(self, ree_id: str) -> tuple[Review, ...]:
        return ReviewSet.model_validate(self._outputs(ree_id, "reviews")).reviews

    def review(self, ree_id: str, review_id: str) -> Review:
        return next(review for review in self.reviews(ree_id) if review.review_id == review_id)

    def review_build_experiment_environment(
        self, ree_id: str, review_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._step(ree_id, "review", "build-experiment-environment", "--basis", basis, "--review-id", review_id)

    def review_activate_experiment_environment(
        self, ree_id: str, review_id: str, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._step(ree_id, "review", "activate-experiment-environment", "--review-id", review_id)

    def review_run_experiment(
        self, ree_id: str, review_id: str, experiment: str, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._step(ree_id, "review", "run-experiment", "--review-id", review_id, experiment)

    def reproduced(self, new_ree: NewRee, fixture: Project) -> Reproduction:
        """Author, seal and sign ``fixture``, and reproduce it in a second REE, which loads it signed."""
        author = new_ree("review-author")
        self.author(author, fixture)
        sealed = self.seal(author, watch=fixture.watch)
        assert sealed.status == "succeeded", self.logs(author, sealed)
        signed = self.sign(author)
        assert signed.status == "succeeded", self.logs(author, signed)
        archive = self.archive(author, "review-baseline")

        reviewer = new_ree("reviewer")
        self.load(reviewer, archive.read_bytes())

        source = self.review_acquire_source(reviewer, "auto", watch=fixture.watch)
        assert source.status == "succeeded", self.logs(reviewer, source)
        review_id = self.reviews(reviewer)[0].review_id

        build = self.review_build_experiment_environment(reviewer, review_id, "auto", watch=fixture.watch)
        assert build.status == "succeeded", self.logs(reviewer, build)
        activation = self.review_activate_experiment_environment(reviewer, review_id, watch=fixture.watch)
        assert activation.status == "succeeded", self.logs(reviewer, activation)
        experiment = self.review_run_experiment(reviewer, review_id, fixture.experiment, watch=fixture.watch)
        logs = self.logs(reviewer, experiment)
        assert experiment.status == "succeeded", logs
        return Reproduction(reviewer, self.review(reviewer, review_id), logs)


def _without_lfs(directory: str, names: list[str]) -> list[str]:
    """What a copy of a history leaves out: the LFS payload store beside the history."""
    return ["lfs"] if Path(directory).name == ".git" and "lfs" in names else []


def _log(stderr: str) -> list[str]:
    """The NDJSON log events a command wrote, as ``[level] message`` lines."""
    lines = []
    for line in stderr.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            lines.append(line)
            continue
        if isinstance(event, dict) and event.get("type") == "log":
            lines.append(f"[{event.get('level')}] {event.get('message')}")
    return lines


def _lines(stderr: str) -> str:
    """The log a command wrote, its last 30 lines as the API keeps them."""
    return "\n".join(_log(stderr)[-30:])


ARCHIVE_DIR = Path(os.environ.get("E2E_ARCHIVE_DIR", "test-artifacts/python/showcase-cli/archives"))
KEPT_REE_DIR = Path(os.environ.get("E2E_KEPT_REE_DIR", "test-artifacts/python/showcase-cli/kept-rees"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get(MACHINE_VARIABLE):
        return
    skip = pytest.mark.skip(reason="the CLI showcases run ree on a machine: run them with just test-showcase-cli")
    for item in items:
        item.add_marker(skip)


@pytest.fixture(scope="session")
def client() -> Client:
    machine = Machine(
        EnvironmentName(os.environ[MACHINE_VARIABLE]),
        os.environ[MACHINE_CONTAINER_VARIABLE],
        Path(os.environ[MACHINE_WORKDIR_VARIABLE]),
    )
    return CliClient(machine, ARCHIVE_DIR, KEPT_REE_DIR, session_file())


@pytest.fixture
def new_ree(client: CliClient, request: pytest.FixtureRequest) -> Iterator[Callable[..., str]]:
    """Create REEs on demand on the test's machine; each is bundled, its histories kept, then removed, when the test
    ends."""
    created: list[str] = []
    label = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower()).strip("-")

    def create(name: str = label) -> str:
        ree_id = client.create(name[:40])
        created.append(ree_id)
        return ree_id

    yield create
    for ree_id in created:
        if client.exists(ree_id):
            client.archive(ree_id, label)
            client.release(ree_id)
