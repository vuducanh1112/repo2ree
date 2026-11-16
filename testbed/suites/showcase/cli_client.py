"""The showcases' steps through ``ree``, run on the test's machine as the user who logs in to it.

The stack under a CLI showcase starts its store's machine as for any showcase; this client works beside the
workbench there, never through it: each step is a ``ree`` command on that machine, against an REE in a directory
the machine and this process share. What a step printed is its log, and its result is the one line ``--json``
writes. ``ree`` runs an REE's scripts on the machine it runs on.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from typed_client import Client, NewRee, Reproduction

from repo2ree_testbed.api_models import (
    AcquirableSourceType,
    Audit,
    CatalogPatch,
    Cpu,
    DefinitionPatch,
    ExperimentPatch,
    HardwarePatch,
    InferenceReport,
    InferenceResult,
    InferenceRule,
    Ree,
    Review,
    ReviewBasis,
    ReviewSet,
    Run,
    ScriptKind,
)
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

BUILD_SCRIPT = "ree-scripts/build_experiment_environment.sh"
ACTIVATE_SCRIPT = "ree-scripts/activate_experiment_environment.sh"
LAUNCH_SCRIPT = "ree-scripts/launch.sh"
# Long enough for a build that pulls and compiles: the command line waits for its step, as a person does.
STEP_SECONDS = 3600


class CliError(AssertionError):
    pass


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

    def ree(self, root: Path, *words: str, stdin: bytes | None = None) -> Done:
        command = machine_exec(ENVIRONMENTS[self.environment], self.container, ["ree", "-C", str(root), *words])
        done = subprocess.run(command, input=stdin or b"", capture_output=True, timeout=STEP_SECONDS, check=False)
        return Done(done.returncode, done.stdout, done.stderr.decode(errors="replace"))


@dataclass
class CliClient:
    """The showcases' steps as ``ree`` commands; an REE is its directory, named by its id."""

    machine: Machine
    archive_dir: Path
    _logs: dict[str, str] = field(default_factory=dict)

    def root(self, ree_id: str) -> Path:
        return self.machine.workdir / ree_id

    # ---- running ree ----------------------------------------------------------

    def _step(self, ree_id: str, *words: str, stdin: bytes | None = None) -> Run:
        """Run one command of the REE's and keep what it logged; the run its result reports."""
        run_id = f"cli-{uuid4().hex[:12]}"
        done = self.machine.ree(self.root(ree_id), "--json", "--run-id", run_id, *words, stdin=stdin)
        self._logs[run_id] = _lines(done.stderr)
        try:
            result = json.loads(done.stdout.decode().strip().splitlines()[-1])
        except (IndexError, ValueError) as exc:
            raise CliError(f"ree {' '.join(words)} wrote no result (exit {done.status}):\n{done.stderr}") from exc
        return Run(run_id=run_id, status=result["status"])

    def _succeed(self, ree_id: str, *words: str, stdin: bytes | None = None) -> Run:
        run = self._step(ree_id, *words, stdin=stdin)
        if run.status != "succeeded":
            raise CliError(f"ree {' '.join(words)} ended {run.status}\n{self._logs[run.run_id]}")
        return run

    def _read(self, ree_id: str, *words: str) -> bytes:
        done = self.machine.ree(self.root(ree_id), *words)
        if done.status != 0:
            raise CliError(f"ree {' '.join(words)} exited {done.status}: {done.stderr}")
        return done.stdout

    def _outputs(self, ree_id: str, *words: str) -> dict[str, Any]:
        run_id = f"cli-{uuid4().hex[:12]}"
        done = self.machine.ree(self.root(ree_id), "--json", "--run-id", run_id, *words)
        self._logs[run_id] = _lines(done.stderr)
        result = json.loads(done.stdout.decode().strip().splitlines()[-1])
        if result["status"] != "succeeded":
            raise CliError(f"ree {' '.join(words)} ended {result['status']}\n{self._logs[run_id]}")
        return dict(result["outputs"])

    def _write(self, ree_id: str, path: str, content: str) -> None:
        self._succeed(ree_id, "write", "--", path, stdin=content.encode())

    def _patch(self, ree_id: str, patch: DefinitionPatch | dict[str, Any]) -> None:
        body = patch.model_dump(exclude_none=True) if isinstance(patch, DefinitionPatch) else patch
        self._succeed(ree_id, "define", stdin=json.dumps(body).encode())

    def _staged(self, data: bytes, name: str) -> Path:
        staged = self.machine.workdir / "uploads" / uuid4().hex / name
        staged.parent.mkdir(parents=True)
        staged.write_bytes(data)
        return staged

    def _proposed(self, ree_id: str, kind: ScriptKind, rule: InferenceRule | str) -> str:
        return self.infer(ree_id, kind).body_of(InferenceRule(rule))

    def create(self, name: str) -> str:
        ree_id = f"{name[:40]}-{uuid4().hex[:8]}"
        done = self.machine.ree(self.root(ree_id), "init", "--name", name)
        if done.status != 0:
            raise CliError(f"ree init exited {done.status}: {done.stderr}")
        return ree_id

    # ---- the Client the showcases use -------------------------------------------

    def logs(self, ree_id: str, run: Run) -> str:
        return self._logs.get(run.run_id, "")

    def ree(self, ree_id: str) -> Ree:
        return Ree.model_validate(json.loads(self._read(ree_id, "show", "--summary"))["ree"])

    def audit(self, ree_id: str) -> Audit:
        return Audit.model_validate(json.loads(self._read(ree_id, "show", "--summary"))["audit"])

    def exists(self, ree_id: str) -> bool:
        return (self.root(ree_id) / "ree.json").is_file()

    def release(self, ree_id: str) -> None:
        subprocess.run(["rm", "-rf", str(self.root(ree_id))], check=False)

    def upload_source(self, ree_id: str, fixture: Project) -> None:
        archive = self._staged(fixture.archive(), fixture.upload_name)
        self._succeed(ree_id, "acquire-source", "--archive", str(archive))

    def fetch_source(self, ree_id: str, origin_url: str, source_type: AcquirableSourceType) -> Run:
        return self._step(
            ree_id, "acquire-source", "--mode", "download", "--origin-url", origin_url, "--source-type", source_type
        )

    def declare_name(self, ree_id: str, name: str) -> None:
        self._patch(ree_id, DefinitionPatch(name=name))

    def declare_catalog(self, ree_id: str, *, version: str, description: str) -> None:
        self._patch(ree_id, DefinitionPatch(catalog=CatalogPatch(version=version, description=description)))

    def declare_cpu(self, ree_id: str, model: str, cpu: Cpu) -> None:
        self._patch(ree_id, DefinitionPatch(hardware=HardwarePatch(cpus={model: cpu})))

    def declare_experiment(self, ree_id: str, fixture: Project) -> None:
        self._write(ree_id, fixture.experiment_script, fixture.recipe("experiment.sh"))
        self._write(ree_id, fixture.experiment_verify, fixture.recipe("experiment.verify.sh"))
        experiment = ExperimentPatch(name=fixture.experiment, output_paths=fixture.outputs)
        self._patch(ree_id, DefinitionPatch(experiments=(experiment,)))

    def evaluate(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "evaluate")

    def infer(self, ree_id: str, kind: ScriptKind, *, experiment: str | None = None) -> InferenceResult:
        target = f"{kind}:{experiment}" if experiment is not None else kind
        [result] = InferenceReport.model_validate(self._outputs(ree_id, "infer", "--target", target)).results
        return result

    def check_working_environment(self, ree_id: str, fixture: Project) -> Run:
        """Write the project's check of what its scripts need, and run it through the launch the project declares."""
        if fixture.launches:
            rule = fixture.rule("launch.sh")
            self._write(
                ree_id, LAUNCH_SCRIPT, self._proposed(ree_id, "launch", rule) if rule else fixture.recipe("launch.sh")
            )
            self._patch(ree_id, {"launch": {}})
        self._write(ree_id, fixture.check_script, fixture.recipe("check_working_environment.sh"))
        return self._step(ree_id, "check-working-environment")

    def build_experiment_environment(self, ree_id: str, fixture: Project, script: str | None = None) -> Run:
        """Check the working environment as the project does, declare the experiment environment, ask inference for
        its build, and build with ``script``, else as the project writes it; a project that launches its scripts
        declares its launch before the check. A check that fails is the step's result, and nothing is built."""
        checked = self.check_working_environment(ree_id, fixture)
        if checked.status != "succeeded":
            return checked
        self._patch(ree_id, {"experiment_environment": {"artifact_path": fixture.experiment_environment_path}})
        proposed = self.infer(ree_id, "build_experiment_environment")
        rule = fixture.rule("build_experiment_environment.sh")
        if script is None:
            script = proposed.body_of(rule) if rule else fixture.recipe("build_experiment_environment.sh")
        self._write(ree_id, BUILD_SCRIPT, script)
        if fixture.rule("activate_experiment_environment.sh") is None:
            self._write(ree_id, ACTIVATE_SCRIPT, fixture.recipe("activate_experiment_environment.sh"))
        return self._step(ree_id, "build-experiment-environment")

    def generate_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "sbom")

    def cross_check_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "sbom-check")

    def activate(self, ree_id: str, fixture: Project) -> Run:
        proposed = self.infer(ree_id, "activate_experiment_environment")
        rule = fixture.rule("activate_experiment_environment.sh")
        if rule:
            self._write(ree_id, ACTIVATE_SCRIPT, proposed.body_of(rule))
        return self._step(ree_id, "test-activation")

    def run_experiment(self, ree_id: str, fixture: Project) -> Run:
        self.declare_experiment(ree_id, fixture)
        self.infer(ree_id, "experiment_run", experiment=fixture.experiment)
        self.infer(ree_id, "experiment_verify", experiment=fixture.experiment)
        return self._step(ree_id, "experiment", fixture.experiment)

    def author(self, ree_id: str, fixture: Project) -> None:
        self.upload_source(ree_id, fixture)
        self._succeed(ree_id, "evaluate")
        self._succeed(ree_id, "hbom")
        for label, run in (
            ("build_experiment_environment", lambda: self.build_experiment_environment(ree_id, fixture)),
            ("activation", lambda: self.activate(ree_id, fixture)),
            ("experiment", lambda: self.run_experiment(ree_id, fixture)),
        ):
            done = run()
            assert done.status == "succeeded", f"{label} ended {done.status}\n{self.logs(ree_id, done)}"

    def seal(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        included = ("--source-included", "--experiment-environment-included", "--results-included")
        return self._step(ree_id, "seal", *included)

    def archive(self, ree_id: str, label: str) -> Path:
        target = self.archive_dir / f"{label}-{ree_id}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._read(ree_id, "bundle"))
        return target

    def load(self, ree_id: str, bundle: bytes) -> None:
        self._succeed(ree_id, "load-bundle", "--archive", str(self._staged(bundle, "ree.zip")))

    def review_source(self, ree_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN) -> Run:
        # The command line names the review it opens; the API names one for its caller.
        return self._step(ree_id, "review", "acquire-source", "--basis", basis, "--", f"review-{uuid4().hex[:12]}")

    def reviews(self, ree_id: str) -> tuple[Review, ...]:
        return ReviewSet.model_validate(json.loads(self._read(ree_id, "reviews"))).reviews

    def review(self, ree_id: str, review_id: str) -> Review:
        return next(review for review in self.reviews(ree_id) if review.review_id == review_id)

    def review_build_experiment_environment(
        self, ree_id: str, review_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._step(ree_id, "review", "build-experiment-environment", "--basis", basis, "--", review_id)

    def review_activation(self, ree_id: str, review_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "review", "test-activation", "--", review_id)

    def review_experiment(self, ree_id: str, review_id: str, experiment: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._step(ree_id, "review", "experiment", "--", review_id, experiment)

    def reproduced(self, new_ree: NewRee, fixture: Project) -> Reproduction:
        """Author and seal ``fixture``, and reproduce it in a second REE."""
        author = new_ree("review-author")
        self.author(author, fixture)
        sealed = self.seal(author, watch=fixture.watch)
        assert sealed.status == "succeeded", self.logs(author, sealed)
        archive = self.archive(author, "review-baseline")

        reviewer = new_ree("reviewer")
        self.load(reviewer, archive.read_bytes())

        source = self.review_source(reviewer, "auto", watch=fixture.watch)
        assert source.status == "succeeded", self.logs(reviewer, source)
        review_id = self.reviews(reviewer)[0].review_id

        build = self.review_build_experiment_environment(reviewer, review_id, "auto", watch=fixture.watch)
        assert build.status == "succeeded", self.logs(reviewer, build)
        activation = self.review_activation(reviewer, review_id, watch=fixture.watch)
        assert activation.status == "succeeded", self.logs(reviewer, activation)
        experiment = self.review_experiment(reviewer, review_id, fixture.experiment, watch=fixture.watch)
        logs = self.logs(reviewer, experiment)
        assert experiment.status == "succeeded", logs
        return Reproduction(reviewer, self.review(reviewer, review_id), logs)


def _lines(stderr: str) -> str:
    """The NDJSON log events a command wrote, as ``[level] message`` lines, its last 30 as the API keeps them."""
    lines = []
    for line in stderr.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            lines.append(line)
            continue
        if isinstance(event, dict) and event.get("type") == "log":
            lines.append(f"[{event.get('level')}] {event.get('message')}")
    return "\n".join(lines[-30:])


ARCHIVE_DIR = Path(os.environ.get("E2E_ARCHIVE_DIR", "test-artifacts/python/showcase-cli/archives"))


@pytest.fixture(scope="session")
def client() -> Client:
    machine = Machine(
        EnvironmentName(os.environ[MACHINE_VARIABLE]),
        os.environ[MACHINE_CONTAINER_VARIABLE],
        Path(os.environ[MACHINE_WORKDIR_VARIABLE]),
    )
    return CliClient(machine, ARCHIVE_DIR)


@pytest.fixture
def new_ree(client: CliClient, request: pytest.FixtureRequest) -> Iterator[Callable[..., str]]:
    """Create REEs on demand on the test's machine; each is bundled, then removed, when the test ends."""
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
