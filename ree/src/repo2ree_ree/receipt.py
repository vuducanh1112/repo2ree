from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_ree.hbom import HBOM
from repo2ree_ree.layout import digest_of
from repo2ree_ree.primitives import (
    ArtifactPath,
    Digest,
    ExperimentEnvironmentPath,
    OverlayPath,
    RunId,
    SourceType,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_ree.workbench_environment import WorkbenchEnvironmentObservation

RECEIPT_SCHEMA_VERSION: Literal[1] = 1

_ARTIFACT_PATH = "definition.experiment_environment.artifact_path"
_BUILD_SCRIPT = "overlay/ree-scripts/build_experiment_environment.sh"
_ACTIVATE_SCRIPT = "overlay/ree-scripts/activate_experiment_environment.sh"
_RUN_SCRIPT = "overlay/ree-scripts/experiments/{experiment_slug}.sh"
_VERIFY_SCRIPT = "overlay/ree-scripts/experiments/{experiment_slug}.verify.sh"
_ENVIRONMENT = ("workspace/{experiment_environment}", "artifacts/{experiment_environment}")

SnapshotDigest = Annotated[Digest, digest_of("file", "snapshot.tar.gz")]
OverlayDigest = Annotated[Digest, digest_of("tree", "overlay")]
ReportDigest = Annotated[Digest, digest_of("file", "artifacts/reproducibility-report.json")]
SbomDigest = Annotated[Digest, digest_of("file", "artifacts/sbom.json")]
BuildScriptDigest = Annotated[Digest, digest_of("file", _BUILD_SCRIPT)]
ActivateScriptDigest = Annotated[Digest, digest_of("file", _ACTIVATE_SCRIPT)]
RunScriptDigest = Annotated[Digest, digest_of("file", _RUN_SCRIPT)]
VerifyScriptDigest = Annotated[Digest | None, digest_of("file", _VERIFY_SCRIPT)]
EnvironmentDigest = Annotated[Digest, digest_of("file", *_ENVIRONMENT, named_by=_ARTIFACT_PATH)]
OptionalEnvironmentDigest = Annotated[Digest | None, digest_of("file", *_ENVIRONMENT, named_by=_ARTIFACT_PATH)]
OutputDigest = Annotated[
    Digest | None, digest_of("paths", "workspace", named_by="definition.experiments[*].output_paths")
]


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_verification_pair(digest: Digest | None, exit_code: int | None) -> None:
    if (digest is None) != (exit_code is None):
        raise ValueError("verification script digest and exit code must be present together")


DriftStatus = Literal["clean", "modified", "unknown"]


class WorkspaceDrift(_ReceiptModel):
    status: DriftStatus
    changed_paths: tuple[WorkspacePath, ...] = ()
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
    snapshot_digest: SnapshotDigest


class EvaluateReproducibilityReceipt(ReceiptEnvelope):
    operation: Literal["evaluate_reproducibility"] = "evaluate_reproducibility"
    snapshot_digest: SnapshotDigest
    overlay_digest: OverlayDigest
    strict: bool
    dependency_level: int = Field(ge=0)
    environment_level: int = Field(ge=0)
    machine_level: int = Field(ge=0)
    dependency_count: int = Field(ge=0)
    manifest_count: int = Field(ge=0)
    report_path: ArtifactPath | None = None
    report_digest: ReportDigest
    analyzer_version: str = Field(min_length=1)


class ObserveHardwareReceipt(ReceiptEnvelope):
    operation: Literal["observe_hardware"] = "observe_hardware"
    observation: HBOM
    observer_version: str = Field(min_length=1)


class BuildExperimentEnvironmentReceipt(ReceiptEnvelope):
    operation: Literal["build_experiment_environment"] = "build_experiment_environment"
    snapshot_digest: SnapshotDigest
    build_experiment_environment_script_path: OverlayPath
    build_experiment_environment_script_digest: BuildScriptDigest
    workspace_drift: WorkspaceDrift
    artifact_path: ExperimentEnvironmentPath
    produced_artifact_digest: EnvironmentDigest
    workbench_environment: WorkbenchEnvironmentObservation | None = None


class GenerateSbomReceipt(ReceiptEnvelope):
    operation: Literal["generate_sbom"] = "generate_sbom"
    experiment_environment_path: ExperimentEnvironmentPath
    experiment_environment_digest: EnvironmentDigest
    sbom_path: ArtifactPath | None = None
    sbom_digest: SbomDigest
    sbom_format: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)


class CrossCheckSbomReceipt(ReceiptEnvelope):
    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    sbom_digest: SbomDigest
    report_digest: ReportDigest
    declared_direct_total: int = Field(ge=0)
    observed_matched: int = Field(ge=0)
    version_mismatches: int = Field(ge=0)
    undeclared_same_ecosystem: int = Field(ge=0)
    observed_total: int = Field(ge=0)


class ActivationReceipt(ReceiptEnvelope):
    """The activate experiment environment script ran a command that does nothing, which exited 0."""

    operation: Literal["activation_test"] = "activation_test"
    snapshot_digest: SnapshotDigest
    experiment_environment_path: ExperimentEnvironmentPath | None = None
    experiment_environment_digest: OptionalEnvironmentDigest = None
    activate_experiment_environment_script_digest: ActivateScriptDigest
    exit_code: Literal[0] = 0
    workbench_environment: WorkbenchEnvironmentObservation | None = None


class RunExperimentReceipt(ReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    snapshot_digest: SnapshotDigest
    experiment_environment_digest: OptionalEnvironmentDigest = None
    activate_experiment_environment_script_digest: ActivateScriptDigest
    run_script_digest: RunScriptDigest
    verify_script_digest: VerifyScriptDigest = None
    run_exit_code: Literal[0] = 0
    verify_exit_code: Literal[0] | None = None
    workbench_environment: WorkbenchEnvironmentObservation | None = None
    produced_output_digest: OutputDigest = None

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
    | ActivationReceipt
    | RunExperimentReceipt,
    Field(discriminator="operation"),
]

receipt_adapter: TypeAdapter[RunReceipt] = TypeAdapter(RunReceipt)
