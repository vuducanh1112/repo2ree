"""What the tiers read and send over the public API, typed: a subset of ``contracts/openapi.json``.

The suites reach the product only as a deployment, so these are written here rather than imported from it;
``testbed/tests/test_api_models.py`` holds them to the contract.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

RunStatus = Literal["queued", "provisioning", "running", "canceling", "succeeded", "failed", "canceled"]
ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ComparisonBasis = Literal["independent", "bundled"]
ReviewBasis = Literal["auto", "independent", "bundled"]
SourceVerdict = Literal["identical", "different", "inconclusive"]
ExperimentEnvironmentVerdict = Literal["identical", "equivalent", "different", "inconclusive"]
ExperimentVerdict = Literal["identical", "reproduced", "different", "inconclusive"]
ReceiptSourceType = Literal["", "git", "hg", "svn", "cvs", "bzr", "tarball", "zip"]
AcquirableSourceType = Literal["git", "tarball", "zip"]
Evidence = Literal["missing", "current", "stale", "not_applicable"]
ScriptKind = Literal[
    "build_experiment_environment",
    "activate_experiment_environment",
    "experiment_run",
    "experiment_verify",
]
InferenceStatus = Literal["complete", "needs_input", "not_inferred"]


class InferenceRule(StrEnum):
    DOCKERFILE = "single-project-root-dockerfile-v1"
    PIP_REQUIREMENTS = "root-pip-requirements-v1"


class InferenceDag(StrEnum):
    BUILD_EXPERIMENT_ENVIRONMENT = "build-experiment-environment-inference"


class _Response(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class _Payload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Run(_Response):
    run_id: str
    status: RunStatus


class SourceComparison(_Response):
    basis: ComparisonBasis
    verdict: SourceVerdict


class ExperimentEnvironmentComparison(_Response):
    basis: ComparisonBasis
    verdict: ExperimentEnvironmentVerdict
    missing_count: int
    extra_count: int


class ExperimentComparison(_Response):
    experiment_name: str
    basis: ComparisonBasis
    verdict: ExperimentVerdict
    observed_verify_exit_code: int | None = None
    expected_output_digest: str | None = None
    observed_output_digest: str | None = None


class Review(_Response):
    review_id: str
    status: ReviewStatus
    source_comparison: SourceComparison | None = None
    experiment_environment_comparison: ExperimentEnvironmentComparison | None = None
    experiment_comparisons: tuple[ExperimentComparison, ...] = ()


class ReviewSet(_Response):
    reviews: tuple[Review, ...] = ()


class SourceReceipt(_Response):
    source_type: ReceiptSourceType
    origin_url: str | None = None
    resolved_revision: str | None = None
    observed_swhid: str | None = None


class SbomReceipt(_Response):
    sbom_path: str | None = None


class Receipts(_Response):
    source: SourceReceipt | None = None
    sbom: SbomReceipt | None = None


class Catalog(_Response):
    version: str = ""
    description: str = ""


class Cpu(_Response):
    vendor: str
    cores_per_cpu: int


class Hardware(_Response):
    cpus: dict[str, Cpu] = {}


class Definition(_Response):
    name: str = ""
    catalog: Catalog = Catalog()
    hardware: Hardware | None = None


class Subject(_Response):
    definition: Definition = Definition()
    receipts: Receipts = Receipts()


class Seal(_Response):
    ree_digest: str


class Ree(_Response):
    subject: Subject = Subject()
    seal: Seal | None = None


class ReeDocument(_Response):
    ree: Ree


class StepAudit(_Response):
    evidence: Evidence


class Audit(_Response):
    source: StepAudit
    evaluation: StepAudit
    experiment_environment: StepAudit
    sbom: StepAudit
    sbom_cross_check: StepAudit
    activation: StepAudit


class ReeState(_Response):
    audit: Audit


class ScriptCandidate(_Response):
    inference_rule: str
    body: str | None


class Decision(_Response):
    dag: str


class InferenceResult(_Response):
    status: InferenceStatus
    candidates: tuple[ScriptCandidate, ...] = ()
    decision: Decision

    def first_body(self) -> str:
        return next(candidate.body for candidate in self.candidates if candidate.body)

    def body_of(self, rule: InferenceRule) -> str:
        return next(
            candidate.body for candidate in self.candidates if candidate.inference_rule == rule and candidate.body
        )

    def rules(self) -> frozenset[str]:
        return frozenset(candidate.inference_rule for candidate in self.candidates)


class InferenceReport(_Response):
    results: tuple[InferenceResult, ...]


class SourceAcquire(_Payload):
    origin_url: str
    source_type: AcquirableSourceType


class SourceReviewRequest(_Payload):
    basis: ReviewBasis


class BuildExperimentEnvironmentReviewRequest(_Payload):
    basis: ReviewBasis


class ScriptTarget(_Payload):
    kind: ScriptKind
    experiment_name: str | None = None


class GenerateScripts(_Payload):
    targets: tuple[ScriptTarget, ...]


class CatalogPatch(_Payload):
    version: str
    description: str


class HardwarePatch(_Payload):
    cpus: dict[str, Cpu]


class ExperimentPatch(_Payload):
    name: str
    output_paths: tuple[str, ...]


class DefinitionPatch(_Payload):
    name: str | None = None
    catalog: CatalogPatch | None = None
    hardware: HardwarePatch | None = None
    experiments: tuple[ExperimentPatch, ...] | None = None


CONTRACT_SCHEMAS: dict[type[BaseModel], str] = {
    Run: "RunSummary",
    SourceComparison: "SourceComparison",
    ExperimentEnvironmentComparison: "ExperimentEnvironmentComparison",
    ExperimentComparison: "ExperimentComparison",
    Review: "ReviewRecord",
    ReviewSet: "ReviewSet",
    SourceReceipt: "AcquireSourceReceipt",
    SbomReceipt: "GenerateSbomReceipt",
    Receipts: "ReeReceipts",
    Catalog: "ReeCatalogMetadata",
    Hardware: "HardwareDefinition",
    Definition: "ReeDefinition-Output",
    Subject: "ReeSubject",
    Seal: "ReeSeal",
    Ree: "Ree",
    ReeDocument: "ReeDocument",
    StepAudit: "StepAudit",
    Audit: "ReeAudit",
    ReeState: "ReeState",
    ScriptCandidate: "ScriptCandidate",
    Decision: "DecisionTrace",
    InferenceResult: "TargetInferenceResult",
    InferenceReport: "InferenceReport",
    SourceAcquire: "SourceAcquirePayload",
    SourceReviewRequest: "CreateSourceReviewPayload",
    BuildExperimentEnvironmentReviewRequest: "CreateBuildExperimentEnvironmentReviewPayload",
    ScriptTarget: "ScriptTargetSelectorPayload",
    GenerateScripts: "GenerateScriptCandidatesPayload",
    CatalogPatch: "ReeCatalogMetadata",
    HardwarePatch: "HardwareDefinition",
    ExperimentPatch: "ExperimentDefinition",
    DefinitionPatch: "ReeDefinition-Input",
}
