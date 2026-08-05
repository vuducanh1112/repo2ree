"""Successful, immutable operation receipts carried by an REE subject.

Attempts which fail or are cancelled are operational run records.  They are
deliberately not representable by this module: a value in :class:`ReeReceipts`
is evidence that the named operation completed successfully.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.domain.primitives import (
    ArtifactPath,
    Digest,
    ReePath,
    RunId,
    SourceType,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_core.time_utils import OperationTiming

RECEIPT_SCHEMA_VERSION: Literal[1] = 1


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class BuildRuntimeReceipt(ReceiptEnvelope):
    operation: Literal["build_runtime"] = "build_runtime"
    snapshot_digest: Digest
    build_runtime_script_path: ReePath
    build_runtime_script_digest: Digest
    workspace_drift: WorkspaceDrift
    runtime_path: WorkspacePath
    produced_runtime_digest: Digest


class GenerateSbomReceipt(ReceiptEnvelope):
    operation: Literal["generate_sbom"] = "generate_sbom"
    runtime_path: WorkspacePath
    runtime_digest: Digest
    sbom_path: ArtifactPath | None = None
    sbom_digest: Digest
    sbom_format: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)


class CrossCheckSbomReceipt(ReceiptEnvelope):
    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    sbom_digest: Digest
    # The reconciliation is a statement about a *pair* of documents, so it has
    # to name both. Without the report digest a re-run evaluation would leave
    # these counts describing a comparison that was never made, with nothing in
    # the receipt able to say so.
    report_digest: Digest
    declared_direct_total: int = Field(ge=0)
    observed_matched: int = Field(ge=0)
    version_mismatches: int = Field(ge=0)
    undeclared_same_ecosystem: int = Field(ge=0)
    observed_total: int = Field(ge=0)


class TestActivationReceipt(ReceiptEnvelope):
    operation: Literal["test_activation"] = "test_activation"
    snapshot_digest: Digest
    runtime_path: WorkspacePath | None = None
    runtime_digest: Digest | None = None
    run_script_digest: Digest
    verify_script_digest: Digest | None = None
    run_exit_code: Literal[0] = 0
    verify_exit_code: Literal[0] | None = None

    @model_validator(mode="after")
    def _verification_pair(self) -> TestActivationReceipt:
        if (self.verify_script_digest is None) != (self.verify_exit_code is None):
            raise ValueError("verification script digest and exit code must be present together")
        return self


class RunExperimentReceipt(ReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    snapshot_digest: Digest
    runtime_digest: Digest | None = None
    run_script_digest: Digest
    verify_script_digest: Digest | None = None
    run_exit_code: Literal[0] = 0
    verify_exit_code: Literal[0] | None = None
    produced_output_digest: Digest | None = None

    @model_validator(mode="after")
    def _verification_pair(self) -> RunExperimentReceipt:
        if (self.verify_script_digest is None) != (self.verify_exit_code is None):
            raise ValueError("verification script digest and exit code must be present together")
        return self


RunReceipt = Annotated[
    AcquireSourceReceipt
    | EvaluateReproducibilityReceipt
    | ObserveHardwareReceipt
    | BuildRuntimeReceipt
    | GenerateSbomReceipt
    | CrossCheckSbomReceipt
    | TestActivationReceipt
    | RunExperimentReceipt,
    Field(discriminator="operation"),
]

receipt_adapter: TypeAdapter[RunReceipt] = TypeAdapter(RunReceipt)


class ReceiptEnvelopeFields(TypedDict):
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int
    recorded_at: UtcInstant


def receipt_envelope(run_id: str, timing: OperationTiming) -> ReceiptEnvelopeFields:
    """Construct the successful receipt envelope for a completed operation."""
    return ReceiptEnvelopeFields(
        run_id=RunId(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
    )
