from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_ree.primitives import (
    Digest,
    GitRevision,
    LaunchOption,
    ReePath,
    RunId,
    SourceHistory,
    SourceType,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_ree.receipt import Launched, LfsFile, OverlayDigest

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ReviewStepKey = Literal[
    "acquire_source", "build_experiment_environment", "activate_experiment_environment", "experiments"
]
ComparisonVerdict = Literal["identical", "different", "inconclusive"]
ExperimentEnvironmentVerdict = Literal["identical", "equivalent", "different", "inconclusive"]
ActivationVerdict = Literal["passed", "failed"]
ExperimentVerdict = Literal["identical", "reproduced", "different", "inconclusive"]

EvidenceBasis = Literal["independent", "bundled"]
ReviewLaunchMode = Literal["author", "native"]


class _ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ReviewExecutionStatus = Literal["succeeded", "failed"]


class ReviewLaunch(_ReviewModel):
    mode: ReviewLaunchMode = "author"
    options: tuple[LaunchOption, ...] = ()

    @model_validator(mode="after")
    def _options_need_a_launch(self) -> ReviewLaunch:
        if self.mode == "native" and self.options:
            raise ValueError("launch options apply to the author's launch, not to a native one")
        return self


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
    expected_revision: GitRevision | None = None
    observed_revision: GitRevision | None = None
    history: SourceHistory | None = None
    lfs_files: tuple[LfsFile, ...] = ()


class ReviewBuildExperimentEnvironmentReceipt(ReviewReceiptEnvelope):
    operation: Literal["build_experiment_environment"] = "build_experiment_environment"
    build_experiment_environment_script_path: ReePath | None = None
    build_experiment_environment_script_digest: Digest | None = None
    artifact_path: WorkspacePath
    produced_artifact_digest: Digest
    overlay_digest: OverlayDigest
    launch_script_digest: Digest | None = None
    launched: Launched | None = None


class ReviewActivateExperimentEnvironmentReceipt(ReviewReceiptEnvelope):
    operation: Literal["activate_experiment_environment"] = "activate_experiment_environment"
    activate_experiment_environment_script_digest: Digest
    exit_code: int | None = None
    experiment_environment_path: WorkspacePath
    experiment_environment_digest: Digest
    launch_script_digest: Digest | None = None
    launched: Launched | None = None


class ReviewRunExperimentReceipt(ReviewReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    activate_experiment_environment_script_digest: Digest
    run_script_path: ReePath
    run_script_digest: Digest
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None
    experiment_environment_path: WorkspacePath | None = None
    experiment_environment_digest: Digest | None = None
    produced_output_digest: Digest | None = None
    launch_script_digest: Digest | None = None
    launched: Launched | None = None


class SourceComparison(_ReviewModel):
    policy: Literal["swhid"] = "swhid"
    basis: EvidenceBasis = "independent"
    expected_swhid: str | None = None
    observed_swhid: str | None = None
    expected_revision: GitRevision | None = None
    observed_revision: GitRevision | None = None
    history_failure: str | None = None
    lfs_failure: str | None = None
    verdict: ComparisonVerdict


class PackageDeltaRecord(_ReviewModel):
    ecosystem: str
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


class ExperimentEnvironmentComparison(_ReviewModel):
    policy: Literal["sbom-closure"] = "sbom-closure"
    basis: EvidenceBasis = "independent"
    verdict: ExperimentEnvironmentVerdict
    expected_artifact_digest: str | None = None
    observed_artifact_digest: str | None = None
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
    policy: Literal["activation"] = "activation"
    basis: EvidenceBasis
    verdict: ActivationVerdict
    experiment_environment_digest: str | None = None
    exit_code: int | None = None


class ExperimentComparison(_ReviewModel):
    policy: Literal["verify-script"] = "verify-script"
    basis: EvidenceBasis
    verdict: ExperimentVerdict
    experiment_name: str
    verify_script_path: str = ""
    expected_verify_script_digest: str | None = None
    verify_script_digest: str | None = None
    expected_activate_experiment_environment_script_digest: str | None = None
    activate_experiment_environment_script_digest: str | None = None
    expected_launch_script_digest: str | None = None
    launch_script_digest: str | None = None
    expected_verify_exit_code: int | None = None
    observed_verify_exit_code: int | None = None
    run_exit_code: int | None = None
    expected_output_digest: str | None = None
    observed_output_digest: str | None = None
    experiment_environment_digest: str | None = None


class ReviewStepState(_ReviewModel):
    step: ReviewStepKey
    status: ReviewStatus
    started_at: UtcInstant
    updated_at: UtcInstant
    failure: str | None = None


class ReviewReceipts(_ReviewModel):
    acquire_source: ReviewAcquireSourceReceipt | None = None
    build_experiment_environment: ReviewBuildExperimentEnvironmentReceipt | None = None
    activate_experiment_environment: ReviewActivateExperimentEnvironmentReceipt | None = None
    experiments: list[ReviewRunExperimentReceipt] = Field(default_factory=list)


class ReviewSubject(_ReviewModel):
    name: str
    version: str = ""
    ree_digest: Digest | None = None
    experiments: tuple[str, ...] = ()


class ReviewMachine(_ReviewModel):
    system: str = Field(min_length=1)
    architecture: str = Field(min_length=1)


class ReviewRecord(_ReviewModel):
    review_id: str
    subject: ReviewSubject
    machine: ReviewMachine
    created_at: UtcInstant
    updated_at: UtcInstant
    status: ReviewStatus
    launch: ReviewLaunch = Field(default_factory=ReviewLaunch)
    steps: list[ReviewStepState] = Field(default_factory=list)
    receipts: ReviewReceipts = Field(default_factory=ReviewReceipts)
    source_comparison: SourceComparison | None = None
    experiment_environment_comparison: ExperimentEnvironmentComparison | None = None
    activation_outcome: ActivationOutcome | None = None
    experiment_comparisons: list[ExperimentComparison] = Field(default_factory=list)
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)
