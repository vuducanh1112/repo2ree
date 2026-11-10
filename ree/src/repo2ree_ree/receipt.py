from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_ree.hbom import HBOM
from repo2ree_ree.primitives import (
    ArtifactPath,
    Digest,
    ReePath,
    RunId,
    SourceType,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_ree.workbench_environment import WorkbenchEnvironmentObservation

RECEIPT_SCHEMA_VERSION: Literal[1] = 1


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_verification_pair(digest: Digest | None, exit_code: int | None) -> None:
    if (digest is None) != (exit_code is None):
        raise ValueError("verification script digest and exit code must be present together")


DriftStatus = Literal["clean", "modified", "unknown"]


class WorkspaceDrift(_ReceiptModel):
    status: DriftStatus
    changed_paths: tuple[ReePath, ...] = ()
    changed_path_count: int = Field(default=0, ge=0)


class ReceiptEnvelope(_ReceiptModel):
    schema_version: Literal[1] = RECEIPT_SCHEMA_VERSION
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int = Field(ge=0)
    recorded_at: UtcInstant

    @model_validator(mode="after")
    def _ordered_timestamps(self) -> ReceiptEnvelope:
        if self.finished_at < self.started_at:
            raise ValueError("receipt finished_at must not precede started_at")
        if self.recorded_at < self.finished_at:
            raise ValueError("receipt recorded_at must not precede finished_at")
        return self


class AcquireSourceReceipt(ReceiptEnvelope):
    operation: Literal["acquire_source"] = "acquire_source"
    origin_url: str | None = None
    source_type: SourceType
    requested_ref: str | None = None
    resolved_revision: str | None = None
    observed_swhid: Swhid | None = None
    snapshot_digest: Digest


class EvaluateReproducibilityReceipt(ReceiptEnvelope):
    operation: Literal["evaluate_reproducibility"] = "evaluate_reproducibility"
    snapshot_digest: Digest
    overlay_digest: Digest
    strict: bool
    dependency_level: int = Field(ge=0)
    environment_level: int = Field(ge=0)
    machine_level: int = Field(ge=0)
    dependency_count: int = Field(ge=0)
    manifest_count: int = Field(ge=0)
    report_path: ArtifactPath | None = None
    report_digest: Digest
    analyzer_version: str = Field(min_length=1)


class ObserveHardwareReceipt(ReceiptEnvelope):
    operation: Literal["observe_hardware"] = "observe_hardware"
    observation: HBOM
    observer_version: str = Field(min_length=1)


class BuildExperimentEnvironmentReceipt(ReceiptEnvelope):
    operation: Literal["build_experiment_environment"] = "build_experiment_environment"
    snapshot_digest: Digest
    build_experiment_environment_script_path: ReePath
    build_experiment_environment_script_digest: Digest
    workspace_drift: WorkspaceDrift
    artifact_path: WorkspacePath
    produced_artifact_digest: Digest
    workbench_environment: WorkbenchEnvironmentObservation | None = None


class GenerateSbomReceipt(ReceiptEnvelope):
    operation: Literal["generate_sbom"] = "generate_sbom"
    experiment_environment_path: WorkspacePath
    experiment_environment_digest: Digest
    sbom_path: ArtifactPath | None = None
    sbom_digest: Digest
    sbom_format: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)


class CrossCheckSbomReceipt(ReceiptEnvelope):
    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    sbom_digest: Digest
    report_digest: Digest
    declared_direct_total: int = Field(ge=0)
    observed_matched: int = Field(ge=0)
    version_mismatches: int = Field(ge=0)
    undeclared_same_ecosystem: int = Field(ge=0)
    observed_total: int = Field(ge=0)


class TestActivationReceipt(ReceiptEnvelope):
    operation: Literal["test_activation"] = "test_activation"
    snapshot_digest: Digest
    experiment_environment_path: WorkspacePath | None = None
    experiment_environment_digest: Digest | None = None
    run_script_digest: Digest
    verify_script_digest: Digest | None = None
    run_exit_code: Literal[0] = 0
    verify_exit_code: Literal[0] | None = None
    workbench_environment: WorkbenchEnvironmentObservation | None = None

    @model_validator(mode="after")
    def _verification_pair(self) -> TestActivationReceipt:
        _require_verification_pair(self.verify_script_digest, self.verify_exit_code)
        return self


class RunExperimentReceipt(ReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    snapshot_digest: Digest
    experiment_environment_digest: Digest | None = None
    run_script_digest: Digest
    verify_script_digest: Digest | None = None
    run_exit_code: Literal[0] = 0
    verify_exit_code: Literal[0] | None = None
    workbench_environment: WorkbenchEnvironmentObservation | None = None
    produced_output_digest: Digest | None = None

    @model_validator(mode="after")
    def _verification_pair(self) -> RunExperimentReceipt:
        _require_verification_pair(self.verify_script_digest, self.verify_exit_code)
        return self


RunReceipt = Annotated[
    AcquireSourceReceipt
    | EvaluateReproducibilityReceipt
    | ObserveHardwareReceipt
    | BuildExperimentEnvironmentReceipt
    | GenerateSbomReceipt
    | CrossCheckSbomReceipt
    | TestActivationReceipt
    | RunExperimentReceipt,
    Field(discriminator="operation"),
]

receipt_adapter: TypeAdapter[RunReceipt] = TypeAdapter(RunReceipt)
