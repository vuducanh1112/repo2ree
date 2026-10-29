from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from repo2ree_protocol.inference import InferenceReport
from repo2ree_protocol.lint import LintReport
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import ReeDefinition
from repo2ree_ree.primitives import Digest, UtcInstant
from repo2ree_ree.receipt import (
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    GenerateSbomReceipt,
    ObserveHardwareReceipt,
    RunExperimentReceipt,
    TestActivationReceipt,
)
from repo2ree_ree.review import (
    ActivationOutcome,
    BuildComparison,
    ExperimentComparison,
    ReviewAcquireSourceReceipt,
    ReviewActivationReceipt,
    ReviewBuildRuntimeReceipt,
    ReviewExperimentReceipt,
    SourceComparison,
)


class NoOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewAcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewAcquireSourceReceipt
    comparison: SourceComparison


class ReviewBuildRuntimeOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewBuildRuntimeReceipt
    comparison: BuildComparison


class ReviewActivationTestOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewActivationReceipt
    outcome: ActivationOutcome


class ReviewRunExperimentOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    experiment_name: str
    receipt: ReviewExperimentReceipt
    comparison: ExperimentComparison


class AcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"]
    origin_url: str | None = None
    source_type: str
    requested_ref: str | None = None
    resolved_revision: str | None = None
    upload_token: str | None = None
    archive_name: str | None = None
    snapshot_digest: str
    swhid: str | None = None


class BundleLoadOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    imported_heads: dict[str, str] = {}
    sealed: bool
    ree_digest: str | None
    source_restored: bool
    overlay_files: int
    artifact_files: int


class LoadReeBundleOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive_name: str
    loaded: BundleLoadOutputs


class VersionConflictOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: Literal["version_conflict"] = "version_conflict"
    path: str | None = None
    expected_version: str
    actual_version: str | None

    def as_outputs(self) -> dict[str, Any]:
        return self.model_dump(exclude={"path"} if self.path is None else set())


class BuildRuntimeOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int
    receipt: BuildRuntimeReceipt


class GenerateSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sbom_relative_path: str
    runtime_relative_path: str
    format: str
    receipt: GenerateSbomReceipt


class CrossCheckSbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_relative_path: str
    sbom_relative_path: str
    cross_check: dict[str, Any]
    receipt: CrossCheckSbomReceipt


class EvaluateOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependency_count: int
    manifest_count: int
    dependency_level: int
    environment_level: int
    machine_level: int
    detected_dependencies: str
    report: dict[str, Any]


class RunnableOperationOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_name: str
    exit_code: int | None = None
    verify_exit_code: int | None = None
    verdict: Literal["pass", "fail"] | None = None
    runtime_path: str = ""
    receipt: TestActivationReceipt | RunExperimentReceipt | None = None


class GenerateHbomOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict[str, Any]
    component_counts: dict[str, int]
    receipt: ObserveHardwareReceipt


class SealOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sealed_at: UtcInstant
    ree_digest: Digest
    input_bytes: int
    entry_count: int


class BuildRuntimeFailureOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int | None


class PatchReeDefinitionOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: str
    definition: ReeDefinition


class LintScriptsOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: list[LintReport]
    missing_scripts: list[str]


OUTPUTS: dict[str, Any] = {
    "review_acquire_source": ReviewAcquireSourceOutputs,
    "review_build_runtime": ReviewBuildRuntimeOutputs,
    "review_activation_test": ReviewActivationTestOutputs,
    "review_run_experiment": ReviewRunExperimentOutputs,
    "materialize_workspace": NoOutputs,
    "acquire_source": AcquireSourceOutputs,
    "load_ree_bundle": LoadReeBundleOutputs,
    "write_file": NoOutputs | VersionConflictOutputs,
    "delete_file": NoOutputs | VersionConflictOutputs,
    "patch_ree_definition": PatchReeDefinitionOutputs | VersionConflictOutputs,
    "remove_source": NoOutputs,
    "build_runtime": BuildRuntimeOutputs | BuildRuntimeFailureOutputs,
    "generate_sbom": GenerateSbomOutputs,
    "cross_check_sbom": CrossCheckSbomOutputs,
    "evaluate_dependency_score": EvaluateOutputs,
    "run_experiment": RunnableOperationOutputs,
    "generate_hbom": GenerateHbomOutputs,
    "activation_test": RunnableOperationOutputs,
    "generate_script_candidates": InferenceReport,
    "lint_scripts": LintScriptsOutputs,
    "seal_ree": SealOutputs,
}

_ADAPTERS = {operation: TypeAdapter(shape) for operation, shape in OUTPUTS.items()}


def outputs_of(operation: str, result: ActionResult) -> BaseModel:
    """The result's outputs as the model its operation declares."""
    model: BaseModel = _ADAPTERS[operation].validate_python(result.outputs)
    return model


def validate_outputs(operation: str, result: ActionResult) -> None:
    """Refuse outputs the operation does not declare; a failed or canceled result may carry none."""
    if result.outputs or result.status == "succeeded":
        outputs_of(operation, result)
