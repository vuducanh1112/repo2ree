"""The API as a client reads it, typed: every stage a method, every response a validated model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest
from system_client import Api

from repo2ree_testbed.api_models import (
    AcquirableSourceType,
    Audit,
    BuildExperimentEnvironmentReviewRequest,
    CatalogPatch,
    Cpu,
    DefinitionPatch,
    ExperimentEnvironmentPatch,
    ExperimentPatch,
    GenerateScripts,
    HardwarePatch,
    InferenceReport,
    InferenceResult,
    Ree,
    ReeDocument,
    ReeState,
    Review,
    ReviewBasis,
    ReviewSet,
    Run,
    ScriptKind,
    ScriptTarget,
    SourceAcquire,
    SourceReviewRequest,
)
from repo2ree_testbed.run_watch import INSTANT_RUN, RunWatch
from repo2ree_testbed.showcases import Project


class NewRee(Protocol):
    def __call__(self, name: str = ...) -> str: ...


@dataclass(frozen=True)
class Reproduction:
    reviewer: str
    review: Review
    logs: str


class Client(Protocol):
    """What a showcase does with an REE, through whichever surface it runs on: the API, or the command line."""

    def logs(self, ree_id: str, run: Run) -> str: ...
    def ree(self, ree_id: str) -> Ree: ...
    def audit(self, ree_id: str) -> Audit: ...
    def exists(self, ree_id: str) -> bool: ...
    def release(self, ree_id: str) -> None: ...
    def upload_source(self, ree_id: str, fixture: Project) -> None: ...
    def fetch_source(self, ree_id: str, origin_url: str, source_type: AcquirableSourceType) -> Run: ...
    def declare_name(self, ree_id: str, name: str) -> None: ...
    def declare_catalog(self, ree_id: str, *, version: str, description: str) -> None: ...
    def declare_cpu(self, ree_id: str, model: str, cpu: Cpu) -> None: ...
    def declare_experiment(self, ree_id: str, fixture: Project) -> None: ...
    def evaluate(self, ree_id: str, *, watch: RunWatch = ...) -> Run: ...
    def infer(self, ree_id: str, kind: ScriptKind, *, experiment: str | None = ...) -> InferenceResult: ...
    def check_working_environment(self, ree_id: str, fixture: Project) -> Run: ...
    def build_experiment_environment(self, ree_id: str, fixture: Project, script: str | None = ...) -> Run: ...
    def generate_sbom(self, ree_id: str, *, watch: RunWatch = ...) -> Run: ...
    def cross_check_sbom(self, ree_id: str, *, watch: RunWatch = ...) -> Run: ...
    def activate(self, ree_id: str, fixture: Project) -> Run: ...
    def run_experiment(self, ree_id: str, fixture: Project) -> Run: ...
    def author(self, ree_id: str, fixture: Project) -> None: ...
    def seal(self, ree_id: str, *, experiment_environment_included: bool = ..., watch: RunWatch = ...) -> Run: ...
    def sign(self, ree_id: str) -> Run: ...
    def sign_review(self, ree_id: str, review_id: str) -> Run: ...
    def archive(self, ree_id: str, label: str) -> Path: ...
    def load(self, ree_id: str, bundle: bytes) -> None: ...
    def review_acquire_source(self, ree_id: str, basis: ReviewBasis, *, watch: RunWatch = ...) -> Run: ...
    def reviews(self, ree_id: str) -> tuple[Review, ...]: ...
    def review(self, ree_id: str, review_id: str) -> Review: ...
    def review_build_experiment_environment(
        self, ree_id: str, review_id: str, basis: ReviewBasis, *, watch: RunWatch = ...
    ) -> Run: ...
    def review_activate_experiment_environment(self, ree_id: str, review_id: str, *, watch: RunWatch = ...) -> Run: ...
    def review_run_experiment(self, ree_id: str, review_id: str, experiment: str, *, watch: RunWatch = ...) -> Run: ...
    def reproduced(self, new_ree: NewRee, fixture: Project) -> Reproduction: ...


@dataclass(frozen=True)
class ApiClient:
    """The showcases' steps over the API, as a deployment's clients make them."""

    api: Api

    def _stage(self, ree_id: str, path: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return Run.model_validate(self.api.stage(ree_id, path, watch=watch))

    def _patch(self, ree_id: str, patch: DefinitionPatch) -> None:
        self.api.patch(ree_id, patch.model_dump(exclude_none=True))

    def logs(self, ree_id: str, run: Run) -> str:
        return str(self.api.logs(ree_id, run.run_id))

    def ree(self, ree_id: str) -> Ree:
        return ReeDocument.model_validate(self.api.get(f"/api/v1/rees/{ree_id}")).ree

    def audit(self, ree_id: str) -> Audit:
        return ReeState.model_validate(self.api.get(f"/api/v1/rees/{ree_id}/state")).audit

    def exists(self, ree_id: str) -> bool:
        return bool(self.api.request("GET", f"/api/v1/rees/{ree_id}", expect=None).status_code != 404)

    def release(self, ree_id: str) -> None:
        self.api.release(ree_id)

    # ---- source ----------------------------------------------------------------

    def upload_source(self, ree_id: str, fixture: Project) -> None:
        self.api.acquire(ree_id, fixture)

    def fetch_source(self, ree_id: str, origin_url: str, source_type: AcquirableSourceType) -> Run:
        request = SourceAcquire(origin_url=origin_url, source_type=source_type)
        run = self.api.post(f"/api/v1/rees/{ree_id}/acquire-source", request.model_dump())
        return Run.model_validate(self.api.wait(ree_id, run))

    # ---- definition ------------------------------------------------------------

    def declare_name(self, ree_id: str, name: str) -> None:
        self._patch(ree_id, DefinitionPatch(name=name))

    def declare_catalog(self, ree_id: str, *, version: str, description: str) -> None:
        self._patch(ree_id, DefinitionPatch(catalog=CatalogPatch(version=version, description=description)))

    def declare_cpu(self, ree_id: str, model: str, cpu: Cpu) -> None:
        self._patch(ree_id, DefinitionPatch(hbom=HardwarePatch(cpus={model: cpu})))

    def declare_experiment(self, ree_id: str, fixture: Project) -> None:
        experiment = ExperimentPatch(name=fixture.experiment, output_paths=fixture.outputs)
        self._patch(ree_id, DefinitionPatch(experiments=(experiment,)))
        self.api.write(ree_id, fixture.experiment_script, fixture.recipe("experiment.sh"))
        self.api.write(ree_id, fixture.experiment_verify, fixture.recipe("experiment.verify.sh"))

    # ---- authoring -------------------------------------------------------------

    def evaluate(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "evaluate-reproducibility", watch=watch)

    def infer(self, ree_id: str, kind: ScriptKind, *, experiment: str | None = None) -> InferenceResult:
        request = GenerateScripts(targets=(ScriptTarget(kind=kind, experiment_name=experiment),))
        response = self.api.post(f"/api/v1/rees/{ree_id}/suggest-scripts", request.model_dump(exclude_none=True))
        [result] = InferenceReport.model_validate(response).results
        return result

    def check_working_environment(self, ree_id: str, fixture: Project) -> Run:
        """Write the project's check of what its scripts need, and run it through the launch the project declares."""
        if fixture.launches:
            self.api.declare_launch(ree_id, fixture)
        self.api.write(ree_id, fixture.check_script, fixture.recipe("check_working_environment.sh"))
        return self._stage(ree_id, "check-working-environment", watch=fixture.watch)

    def build_experiment_environment(self, ree_id: str, fixture: Project, script: str | None = None) -> Run:
        """Check the working environment as the project does, declare the experiment environment, ask inference for
        its build, and build with ``script``, else as the project writes it: what inference proposed by the project's
        rule, or the recipe's. A check that fails is the step's result, and nothing is built."""
        checked = self.check_working_environment(ree_id, fixture)
        if checked.status != "succeeded":
            return checked
        artifact = ExperimentEnvironmentPatch(artifact_path=fixture.experiment_environment_path)
        self._patch(ree_id, DefinitionPatch(experiment_environment=artifact))
        proposed = self.infer(ree_id, "build_experiment_environment")
        rule = fixture.rule("build_experiment_environment.sh")
        if script is None and rule:
            script = proposed.body_of(rule)
        return Run.model_validate(self.api.build_experiment_environment(ree_id, script, fixture=fixture))

    def generate_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "generate-sbom", watch=watch)

    def cross_check_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "cross-check-sbom", watch=watch)

    def activate(self, ree_id: str, fixture: Project) -> Run:
        """Ask inference for the activate script of the environment just built, then test it as the project writes
        it: what inference proposed by the project's rule, or the recipe's."""
        proposed = self.infer(ree_id, "activate_experiment_environment")
        rule = fixture.rule("activate_experiment_environment.sh")
        script = proposed.body_of(rule) if rule else None
        return Run.model_validate(self.api.activate(ree_id, script, fixture=fixture))

    def run_experiment(self, ree_id: str, fixture: Project) -> Run:
        """Declare the experiment with the recipe's scripts, which declaring it requires, ask inference for its run
        and verify scripts, which it infers from the source and the declarations alone, then run the recipe's."""
        self.declare_experiment(ree_id, fixture)
        self.infer(ree_id, "experiment_run", experiment=fixture.experiment)
        self.infer(ree_id, "experiment_verify", experiment=fixture.experiment)
        return Run.model_validate(self.api.experiment(ree_id, fixture=fixture))

    def author(self, ree_id: str, fixture: Project) -> None:
        """Every authoring stage, inference asked for each script before the recipe's is written."""
        self.api.acquire(ree_id, fixture)
        self.api.succeed(ree_id, "evaluate-reproducibility", watch=fixture.watch)
        self.api.succeed(ree_id, "observe-hardware")
        for label, run in (
            ("build_experiment_environment", lambda: self.build_experiment_environment(ree_id, fixture)),
            ("activation", lambda: self.activate(ree_id, fixture)),
            ("experiment", lambda: self.run_experiment(ree_id, fixture)),
        ):
            done = run()
            assert done.status == "succeeded", f"{label} ended {done.status}\n{self.logs(ree_id, done)}"

    def seal(self, ree_id: str, *, experiment_environment_included: bool = True, watch: RunWatch = INSTANT_RUN) -> Run:
        sealed = self.api.seal(ree_id, experiment_environment_included=experiment_environment_included, watch=watch)
        return Run.model_validate(sealed)

    def sign(self, ree_id: str) -> Run:
        return Run.model_validate(self.api.sign(ree_id))

    def sign_review(self, ree_id: str, review_id: str) -> Run:
        return Run.model_validate(self.api.sign_review(ree_id, review_id))

    def archive(self, ree_id: str, label: str) -> Path:
        kept: Path | None = self.api.keep_archive(ree_id, label)
        assert kept is not None, "the archive was refused"
        return kept

    # ---- review ----------------------------------------------------------------

    def load(self, ree_id: str, bundle: bytes) -> None:
        self.api.load(ree_id, bundle)

    def review_acquire_source(self, ree_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN) -> Run:
        request = SourceReviewRequest(basis=basis)
        run = self.api.stage(ree_id, "reviews/acquire-source", request.model_dump(), watch=watch)
        return Run.model_validate(run)

    def reviews(self, ree_id: str) -> tuple[Review, ...]:
        return ReviewSet.model_validate(self.api.get(f"/api/v1/rees/{ree_id}/reviews")).reviews

    def review(self, ree_id: str, review_id: str) -> Review:
        return Review.model_validate(self.api.get(f"/api/v1/rees/{ree_id}/reviews/{review_id}"))

    def review_build_experiment_environment(
        self, ree_id: str, review_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        request = BuildExperimentEnvironmentReviewRequest(basis=basis)
        run = self.api.stage(
            ree_id, f"reviews/{review_id}/build-experiment-environment", request.model_dump(), watch=watch
        )
        return Run.model_validate(run)

    def review_activate_experiment_environment(
        self, ree_id: str, review_id: str, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._stage(ree_id, f"reviews/{review_id}/activate-experiment-environment", watch=watch)

    def review_run_experiment(
        self, ree_id: str, review_id: str, experiment: str, *, watch: RunWatch = INSTANT_RUN
    ) -> Run:
        return self._stage(ree_id, f"reviews/{review_id}/run-experiment/{experiment}", watch=watch)

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


@pytest.fixture(scope="session")
def client(api: Api) -> Client:
    return ApiClient(api)
