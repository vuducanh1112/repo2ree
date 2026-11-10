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
    BuildReviewRequest,
    CatalogPatch,
    Cpu,
    DefinitionPatch,
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
    def __call__(self, name: str = ..., *, image: str | None = ...) -> str: ...


@dataclass(frozen=True)
class Reproduction:
    reviewer: str
    review: Review
    logs: str


@dataclass(frozen=True)
class Client:
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
        run = self.api.post(f"/api/v1/rees/{ree_id}/source:acquire", request.model_dump())
        return Run.model_validate(self.api.wait(ree_id, run))

    # ---- definition ------------------------------------------------------------

    def declare_name(self, ree_id: str, name: str) -> None:
        self._patch(ree_id, DefinitionPatch(name=name))

    def declare_catalog(self, ree_id: str, *, version: str, description: str) -> None:
        self._patch(ree_id, DefinitionPatch(catalog=CatalogPatch(version=version, description=description)))

    def declare_cpu(self, ree_id: str, model: str, cpu: Cpu) -> None:
        self._patch(ree_id, DefinitionPatch(hardware=HardwarePatch(cpus={model: cpu})))

    def declare_experiment(self, ree_id: str, fixture: Project) -> None:
        self.api.write(ree_id, fixture.experiment_script, fixture.recipe("experiment.sh"))
        self.api.write(ree_id, fixture.experiment_verify, fixture.recipe("experiment.verify.sh"))
        experiment = ExperimentPatch(name=fixture.experiment, output_paths=fixture.outputs)
        self._patch(ree_id, DefinitionPatch(experiments=(experiment,)))

    # ---- authoring -------------------------------------------------------------

    def evaluate(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "evaluate", watch=watch)

    def infer(self, ree_id: str, kind: ScriptKind, *, experiment: str | None = None) -> InferenceResult:
        request = GenerateScripts(targets=(ScriptTarget(kind=kind, experiment_name=experiment),))
        response = self.api.post(
            f"/api/v1/rees/{ree_id}/script-inferences:generate", request.model_dump(exclude_none=True)
        )
        [result] = InferenceReport.model_validate(response).results
        return result

    def build(self, ree_id: str, fixture: Project) -> Run:
        return Run.model_validate(self.api.build(ree_id, fixture=fixture))

    def generate_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "generate-sbom", watch=watch)

    def cross_check_sbom(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, "cross-check-sbom", watch=watch)

    def activate(self, ree_id: str, fixture: Project) -> Run:
        return Run.model_validate(self.api.activate(ree_id, fixture=fixture))

    def run_experiment(self, ree_id: str, fixture: Project) -> Run:
        return Run.model_validate(self.api.experiment(ree_id, fixture=fixture))

    def author(self, ree_id: str, fixture: Project) -> None:
        self.api.author(ree_id, fixture)

    def seal(self, ree_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return Run.model_validate(self.api.seal(ree_id, watch=watch))

    def archive(self, ree_id: str, label: str) -> Path:
        kept: Path | None = self.api.keep_archive(ree_id, label)
        assert kept is not None, "the archive was refused"
        return kept

    # ---- review ----------------------------------------------------------------

    def load(self, ree_id: str, bundle: bytes) -> None:
        self.api.load(ree_id, bundle)

    def review_source(self, ree_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN) -> Run:
        request = SourceReviewRequest(basis=basis)
        run = self.api.stage(ree_id, "reviews/source:reproduce", request.model_dump(), watch=watch)
        return Run.model_validate(run)

    def reviews(self, ree_id: str) -> tuple[Review, ...]:
        return ReviewSet.model_validate(self.api.get(f"/api/v1/rees/{ree_id}/reviews")).reviews

    def review(self, ree_id: str, review_id: str) -> Review:
        return Review.model_validate(self.api.get(f"/api/v1/rees/{ree_id}/reviews/{review_id}"))

    def review_build(self, ree_id: str, review_id: str, basis: ReviewBasis, *, watch: RunWatch = INSTANT_RUN) -> Run:
        request = BuildReviewRequest(basis=basis)
        run = self.api.stage(ree_id, f"reviews/{review_id}/build:reproduce", request.model_dump(), watch=watch)
        return Run.model_validate(run)

    def review_activation(self, ree_id: str, review_id: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, f"reviews/{review_id}/activation:reproduce", watch=watch)

    def review_experiment(self, ree_id: str, review_id: str, experiment: str, *, watch: RunWatch = INSTANT_RUN) -> Run:
        return self._stage(ree_id, f"reviews/{review_id}/experiments/{experiment}:reproduce", watch=watch)

    def reproduced(self, new_ree: NewRee, fixture: Project) -> Reproduction:
        """Author and seal ``fixture``, and reproduce it in a second REE."""
        author = new_ree("review-author", image=fixture.image)
        self.author(author, fixture)
        sealed = self.seal(author, watch=fixture.watch)
        assert sealed.status == "succeeded", self.logs(author, sealed)
        archive = self.archive(author, "review-baseline")

        reviewer = new_ree("reviewer", image=fixture.image)
        self.load(reviewer, archive.read_bytes())

        source = self.review_source(reviewer, "auto", watch=fixture.watch)
        assert source.status == "succeeded", self.logs(reviewer, source)
        review_id = self.reviews(reviewer)[0].review_id

        build = self.review_build(reviewer, review_id, "auto", watch=fixture.watch)
        assert build.status == "succeeded", self.logs(reviewer, build)
        activation = self.review_activation(reviewer, review_id, watch=fixture.watch)
        assert activation.status == "succeeded", self.logs(reviewer, activation)
        experiment = self.review_experiment(reviewer, review_id, fixture.experiment, watch=fixture.watch)
        logs = self.logs(reviewer, experiment)
        assert experiment.status == "succeeded", logs
        return Reproduction(reviewer, self.review(reviewer, review_id), logs)


@pytest.fixture(scope="session")
def client(api: Api) -> Client:
    return Client(api)
