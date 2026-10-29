from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.primitives import Digest, ReePath, RunId, SourceType, Swhid, UtcInstant, WorkspacePath

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ReviewStepKey = Literal["source", "build", "activation", "experiments"]
ComparisonVerdict = Literal["identical", "different", "inconclusive"]
BuildVerdict = Literal["identical", "equivalent", "different", "inconclusive"]
ActivationVerdict = Literal["passed", "failed"]
ExperimentVerdict = Literal["identical", "reproduced", "different", "inconclusive"]

EvidenceBasis = Literal["independent", "bundled"]


class _ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ReviewExecutionStatus = Literal["succeeded", "failed"]


class ReviewReceiptEnvelope(_ReviewModel):
    schema_version: Literal[1] = 1
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int = Field(ge=0)
    recorded_at: UtcInstant
    status: ReviewExecutionStatus


class ReviewAcquireSourceReceipt(ReviewReceiptEnvelope):
    operation: Literal["acquire_source"] = "acquire_source"
    origin_url: str | None = None
    source_type: SourceType
    requested_ref: str | None = None
    expected_swhid: Swhid | None = None
    observed_swhid: Swhid | None = None


class ReviewBuildRuntimeReceipt(ReviewReceiptEnvelope):
    operation: Literal["build_runtime"] = "build_runtime"
    build_runtime_script_path: ReePath | None = None
    build_runtime_script_digest: Digest | None = None
    runtime_path: WorkspacePath
    produced_runtime_digest: Digest


class ReviewActivationReceipt(ReviewReceiptEnvelope):
    operation: Literal["test_activation"] = "test_activation"
    run_script_path: ReePath
    run_script_digest: Digest
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None
    runtime_path: WorkspacePath
    runtime_digest: Digest


class ReviewExperimentReceipt(ReviewReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    run_script_path: ReePath
    run_script_digest: Digest
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None
    runtime_path: WorkspacePath | None = None
    runtime_digest: Digest | None = None
    produced_output_digest: Digest | None = None


class SourceComparison(_ReviewModel):
    policy: Literal["swhid"] = "swhid"
    basis: EvidenceBasis = "independent"
    expected_swhid: str | None = None
    observed_swhid: str | None = None
    verdict: ComparisonVerdict


class PackageDeltaRecord(_ReviewModel):
    ecosystem: str
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


class BuildComparison(_ReviewModel):
    policy: Literal["sbom-closure"] = "sbom-closure"
    basis: EvidenceBasis = "independent"
    verdict: BuildVerdict
    expected_runtime_digest: str | None = None
    observed_runtime_digest: str | None = None
    expected_sbom_digest: str | None = None
    observed_sbom_digest: str | None = None
    sbom_tool_version: str | None = None
    expected_package_total: int = 0
    observed_package_total: int = 0
    matched: int = 0
    missing_count: int = 0
    extra_count: int = 0
    version_mismatch_count: int = 0
    advisory_count: int = 0
    missing: list[PackageDeltaRecord] = Field(default_factory=list)
    extra: list[PackageDeltaRecord] = Field(default_factory=list)
    version_mismatches: list[PackageDeltaRecord] = Field(default_factory=list)
    advisory: list[PackageDeltaRecord] = Field(default_factory=list)


class ActivationOutcome(_ReviewModel):
    policy: Literal["activation-probe"] = "activation-probe"
    basis: EvidenceBasis
    verdict: ActivationVerdict
    runtime_digest: str | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None


class ExperimentComparison(_ReviewModel):
    policy: Literal["verify-script"] = "verify-script"
    basis: EvidenceBasis
    verdict: ExperimentVerdict
    experiment_name: str
    verify_script_path: str = ""
    expected_verify_script_digest: str | None = None
    verify_script_digest: str | None = None
    expected_verify_exit_code: int | None = None
    observed_verify_exit_code: int | None = None
    run_exit_code: int | None = None
    expected_output_digest: str | None = None
    observed_output_digest: str | None = None
    runtime_digest: str | None = None


class ReviewStepState(_ReviewModel):
    step: ReviewStepKey
    status: ReviewStatus
    started_at: str
    updated_at: str
    failure: str | None = None


class ReviewRecord(_ReviewModel):
    review_id: str
    created_at: str
    updated_at: str
    status: ReviewStatus
    steps: list[ReviewStepState] = Field(default_factory=list)
    source_receipt: ReviewAcquireSourceReceipt | None = None
    source_comparison: SourceComparison | None = None
    build_receipt: ReviewBuildRuntimeReceipt | None = None
    build_comparison: BuildComparison | None = None
    activation_receipt: ReviewActivationReceipt | None = None
    activation_outcome: ActivationOutcome | None = None
    experiment_receipts: list[ReviewExperimentReceipt] = Field(default_factory=list)
    experiment_comparisons: list[ExperimentComparison] = Field(default_factory=list)
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)
