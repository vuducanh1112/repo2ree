"""The showcases' steps through ``ree``, run on the test's machine as the user who logs in to it.

The stack under a CLI showcase starts its store's machine as for any showcase; this client works beside the
workbench there, never through it: each step is a ``ree`` command on that machine, typed in the REE's directory,
which the machine and this process share. A step prints what a person reads, which the recording keeps; its result,
as ``--json`` would print it, goes to a file beside, where this client reads it. ``ree`` runs an REE's scripts on the
machine it runs on.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterator
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
from repo2ree_testbed.cli_cast import append_command, cast_file
from repo2ree_testbed.cli_machine import Done, Machine, keep_histories
from repo2ree_testbed.cli_session import LOG_LINES, CliCommand, append, kept_result, kept_stdin, session_file
from repo2ree_testbed.run_watch import INSTANT_RUN, RunWatch
from repo2ree_testbed.showcases import Project
from repo2ree_testbed.stack.environments import (
    MACHINE_VARIABLE,
)
from repo2ree_testbed.stack.sigstore import local_sigstore

BUILD_SCRIPT = "ree-scripts/build_experiment_environment.sh"
LAUNCH_SCRIPT = "ree-scripts/launch.sh"


class CliError(AssertionError):
    pass


class Result(BaseModel):
    """What ``ree --result-file`` writes: how the command ended and what it found."""

    model_config = ConfigDict(extra="ignore")

    status: RunStatus
    outputs: dict[str, Any] = Field(default_factory=dict)


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
    # The same commands as a terminal recording (cli_cast).
    cast: Path | None = None
    _logs: dict[str, str] = field(default_factory=dict)

    def root(self, ree_id: str) -> Path:
        return self.machine.workdir / ree_id

    def _here(self, ree_id: str, path: Path) -> str:
        """``path`` as typed in the REE's directory."""
        return os.path.relpath(path, self.root(ree_id))

    # ---- running ree ----------------------------------------------------------

    def _result(
        self, ree_id: str, *words: str, stdin: bytes | None = None, variables: dict[str, str] | None = None
    ) -> tuple[str, Result]:
        """Run one command of the REE's and keep what it logged; its run and the result it wrote."""
        run_id = f"cli-{uuid4().hex[:12]}"
        written = self.machine.workdir / "results" / f"{run_id}.json"
        written.parent.mkdir(parents=True, exist_ok=True)
        plumbing = ("--run-id", run_id, "--result-file", self._here(ree_id, written))
        done = self._ree(ree_id, words, stdin, run_id, variables, plumbing=plumbing, result=written)
        self._logs[run_id] = _lines(done.stderr)
        try:
            return run_id, Result.model_validate_json(written.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
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
        *,
        plumbing: tuple[str, ...] = (),
        result: Path | None = None,
    ) -> Done:
        """Run one ``ree`` command in the REE's directory, and add it to the test's session and recording as a person
        types it: ``plumbing``, the options that name its run and its result file, is left out of both."""
        started = time.time()
        done = self.machine.ree(self.root(ree_id), *plumbing, *words, stdin=stdin, variables=variables)
        if self.session is not None:
            kept, result_bytes = (
                kept_result(result.read_text(encoding="utf-8").strip())
                if result is not None and result.is_file()
                else (None, 0)
            )
            text, stdin_bytes = kept_stdin(stdin)
            command = CliCommand(
                ree=ree_id,
                words=words,
                run_id=run_id,
                stdin=text,
                stdin_bytes=stdin_bytes,
                exit=done.status,
                result=kept,
                result_bytes=result_bytes,
                stdout_bytes=len(done.stdout),
                log=tuple(done.stderr.splitlines()[-LOG_LINES:]),
                started=started,
                finished=time.time(),
            )
            append(self.session, command)
        if self.cast is not None:
            append_command(
                self.cast,
                ("ree", *words),
                where=ree_id,
                stdin_bytes=len(stdin or b""),
                started=started,
                finished=time.time(),
                printed=done.printed,
            )
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

    def _staged(self, ree_id: str, data: bytes, name: str) -> str:
        """Put ``data`` where the machine reads it, and name it as typed in the REE's directory."""
        staged = self.machine.workdir / "uploads" / uuid4().hex[:8] / name
        staged.parent.mkdir(parents=True)
        staged.write_bytes(data)
        return self._here(ree_id, staged)

    def create(self, name: str) -> str:
        """Create an REE, and its kept folder: one with no history in it is an REE whose history went unkept."""
        ree_id = f"{name[:40]}-{uuid4().hex[:8]}"
        (self.kept_dir / ree_id).mkdir(parents=True, exist_ok=True)
        self.root(ree_id).mkdir(parents=True)
        self._outputs(ree_id, "initialize-ree", "--name", name)
        return ree_id

    def _keep(self, ree_id: str) -> None:
        keep_histories(self.root(ree_id), self.kept_dir / ree_id)

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
        archive = self._staged(ree_id, fixture.archive(), fixture.upload_name)
        self._outputs(ree_id, "acquire-source", "--archive", archive)

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

    def seal(self, ree_id: str, *, experiment_environment_included: bool = True, watch: RunWatch = INSTANT_RUN) -> Run:
        left_out = () if experiment_environment_included else ("--no-experiment-environment-included",)
        return self._step(ree_id, "seal-ree", *left_out)

    def sign(self, ree_id: str) -> Run:
        """Sign the sealed REE with the run's Sigstore as its author: signed in by a token in the environment, never
        among the words typed. Its author's signature verifies, and no reviewer's would."""
        local = local_sigstore()
        signed = self._signed_as(ree_id, local.author, "sign-ree")
        if signed.status == "succeeded":
            self._verified(ree_id, signer=local.author, other=local.reviewer)
        return signed

    def sign_review(self, ree_id: str, review_id: str) -> Run:
        """Sign the review with the run's Sigstore as its reviewer: the record is the statement's predicate. Its
        reviewer's signature verifies, and no author's would."""
        local = local_sigstore()
        signed = self._signed_as(ree_id, local.reviewer, "sign-review", "--review-id", review_id)
        if signed.status == "succeeded":
            self._verified(ree_id, "--review-id", review_id, signer=local.reviewer, other=local.author)
        return signed

    def _signed_as(self, ree_id: str, signer: str, *words: str) -> Run:
        trust = self._staged(ree_id, local_sigstore().trust_config.read_bytes(), "trust_config.json")
        token = {"SIGSTORE_IDENTITY_TOKEN": local_sigstore().token(signer)}
        return self._step(ree_id, *words, "--trust-config", trust, variables=token)

    def _verification(self, ree_id: str, *words: str, signer: str) -> list[str]:
        """What ``ree verify-signatures`` finds of each signature against the run's Sigstore, naming ``signer``."""
        local = local_sigstore()
        trust = self._staged(ree_id, local.trust_config.read_bytes(), "trust_config.json")
        policy = ("--identity", signer, "--issuer", local.issuer, "--trust-config", trust)
        _, result = self._result(ree_id, "verify-signatures", *words, *policy)
        return [str(item["outcome"]) for item in result.outputs["signatures"]]

    def _verified(self, ree_id: str, *words: str, signer: str, other: str) -> None:
        """Each signature verifies under a policy naming its signer, and is the other signer's under one naming the
        other."""
        verified = self._verification(ree_id, *words, signer=signer)
        assert verified, f"nothing signed in {ree_id} {' '.join(words)}"
        assert set(verified) == {"verified"}, verified
        assert set(self._verification(ree_id, *words, signer=other)) == {"other_signer"}

    def archive(self, ree_id: str, label: str) -> Path:
        target = self.archive_dir / f"{label}-{ree_id}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._bytes(ree_id, "bundle"))
        return target

    def load(self, ree_id: str, bundle: bytes) -> None:
        self._outputs(ree_id, "load-ree-bundle", "--archive", self._staged(ree_id, bundle, "ree.zip"))

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
        """Author, seal and sign ``fixture``, reproduce it in a second REE, which loads it signed, and sign the
        review."""
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
        signed_review = self.sign_review(reviewer, review_id)
        assert signed_review.status == "succeeded", self.logs(reviewer, signed_review)
        return Reproduction(reviewer, self.review(reviewer, review_id), logs)


def _lines(stderr: str) -> str:
    """The log a command wrote, its last 30 lines as the API keeps them."""
    return "\n".join(stderr.splitlines()[-30:])


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
    machine = Machine.of_this_test()
    if machine is None:
        raise RuntimeError("the CLI showcases run ree on a machine the stack starts for each test")
    return CliClient(machine, ARCHIVE_DIR, KEPT_REE_DIR, session_file(), cast_file())


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
