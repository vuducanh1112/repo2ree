from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from repo2ree_ree.digest import digest_json
from repo2ree_ree.hbom import HBOM
from repo2ree_ree.layout import digest_of
from repo2ree_ree.primitives import (
    Digest,
    ExperimentEnvironmentPath,
    OverlayPath,
    ReePath,
    SourceType,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_ree.receipt import (
    AcquireSourceReceipt,
    ActivateExperimentEnvironmentReceipt,
    ActivateScriptDigest,
    BuildExperimentEnvironmentReceipt,
    BuildScriptDigest,
    CheckScriptDigest,
    CheckWorkingEnvironmentReceipt,
    CrossCheckSbomReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    LaunchScriptDigest,
    ObserveHardwareReceipt,
    RunExperimentReceipt,
    RunScriptDigest,
    VerifyScriptDigest,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
    experiment_run_script_path,
    experiment_slug,
    experiment_verify_script_path,
    is_overlay_path,
)

CURRENT_SCHEMA_VERSION: Literal[1] = 1


class _DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Contributor(_DomainModel):
    identifier: str = ""
    name: str = ""
    affiliation_name: str = ""
    affiliation_identifier: str = ""


class ReeCatalogMetadata(_DomainModel):
    description: str = ""
    version: str = ""
    website: str = ""
    keywords: tuple[str, ...] = ()
    contributors: tuple[Contributor, ...] = ()
    corresponding_author_identifier: str | None = None


class SourceDefinition(_DomainModel):
    origin_url: str | None = None
    source_type: SourceType
    requested_ref: str | None = None

    @model_validator(mode="after")
    def _complete_source(self) -> SourceDefinition:
        if not self.source_type:
            raise ValueError("a present source definition requires a source type")
        return self


class ExperimentEnvironmentDefinition(_DomainModel):
    build_experiment_environment_script_path: OverlayPath = OverlayPath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
    build_experiment_environment_script_digest: BuildScriptDigest
    build_experiment_environment_script_size: int = Field(ge=0)
    artifact_path: ExperimentEnvironmentPath | None = None

    @field_validator("build_experiment_environment_script_path")
    @classmethod
    def _fixed_path(cls, value: OverlayPath) -> OverlayPath:
        if value != RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT:
            raise ValueError(
                f"build experiment environment script path must be {RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT!r}"
            )
        return value


class ActivateExperimentEnvironmentDefinition(_DomainModel):
    activate_experiment_environment_script_path: OverlayPath = OverlayPath(
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT
    )
    activate_experiment_environment_script_digest: ActivateScriptDigest
    activate_experiment_environment_script_size: int = Field(ge=0)

    @field_validator("activate_experiment_environment_script_path")
    @classmethod
    def _fixed_path(cls, value: OverlayPath) -> OverlayPath:
        if value != RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT:
            expected = RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT
            raise ValueError(f"activate experiment environment script path must be {expected!r}")
        return value


class LaunchDefinition(_DomainModel):
    launch_script_path: OverlayPath = OverlayPath(RESERVED_LAUNCH_SCRIPT)
    launch_script_digest: LaunchScriptDigest
    launch_script_size: int = Field(ge=0)

    @field_validator("launch_script_path")
    @classmethod
    def _fixed_path(cls, value: OverlayPath) -> OverlayPath:
        if value != RESERVED_LAUNCH_SCRIPT:
            raise ValueError(f"launch script path must be {RESERVED_LAUNCH_SCRIPT!r}")
        return value


class CheckWorkingEnvironmentDefinition(_DomainModel):
    check_working_environment_script_path: OverlayPath = OverlayPath(RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT)
    check_working_environment_script_digest: CheckScriptDigest
    check_working_environment_script_size: int = Field(ge=0)

    @field_validator("check_working_environment_script_path")
    @classmethod
    def _fixed_path(cls, value: OverlayPath) -> OverlayPath:
        if value != RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT:
            raise ValueError(f"check script path must be {RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT!r}")
        return value


class ExperimentDefinition(_DomainModel):
    name: str = Field(min_length=1)
    run_script_path: OverlayPath
    run_script_digest: RunScriptDigest
    run_script_size: int = Field(ge=0)
    verify_script_path: OverlayPath
    verify_script_digest: VerifyScriptDigest
    verify_script_size: int = Field(ge=0)
    output_paths: tuple[WorkspacePath, ...] = ()

    @model_validator(mode="after")
    def _conventional_paths(self) -> ExperimentDefinition:
        if self.run_script_path != experiment_run_script_path(self.name):
            raise ValueError("experiment run script path must be derived from its name")
        if self.verify_script_path != experiment_verify_script_path(self.name):
            raise ValueError("experiment verification script path must be derived from its name")
        if len(self.output_paths) != len(set(self.output_paths)):
            raise ValueError("experiment output paths must be unique")
        return self


class HardwareDefinition(HBOM):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReeDefinition(_DomainModel):
    name: str = ""
    catalog: ReeCatalogMetadata = Field(default_factory=ReeCatalogMetadata)
    source: SourceDefinition | None = None
    experiment_environment: ExperimentEnvironmentDefinition
    activate_experiment_environment: ActivateExperimentEnvironmentDefinition
    check_working_environment: CheckWorkingEnvironmentDefinition
    launch: LaunchDefinition
    hbom: HardwareDefinition | None = None
    experiments: tuple[ExperimentDefinition, ...] = ()

    @model_validator(mode="after")
    def _unique_experiments(self) -> ReeDefinition:
        names = [experiment.name for experiment in self.experiments]
        slugs = [experiment_slug(name) for name in names]
        if len(names) != len(set(names)):
            raise ValueError("experiment names must be unique")
        if len(slugs) != len(set(slugs)):
            raise ValueError("experiment slugs must be unique")
        return self


class ReeReceipts(_DomainModel):
    acquire_source: AcquireSourceReceipt | None = None
    evaluate_reproducibility: EvaluateReproducibilityReceipt | None = None
    observe_hardware: ObserveHardwareReceipt | None = None
    check_working_environment: CheckWorkingEnvironmentReceipt | None = None
    build_experiment_environment: BuildExperimentEnvironmentReceipt | None = None
    generate_sbom: GenerateSbomReceipt | None = None
    cross_check_sbom: CrossCheckSbomReceipt | None = None
    activate_experiment_environment: ActivateExperimentEnvironmentReceipt | None = None
    experiments: dict[str, RunExperimentReceipt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _experiment_keys_match(self) -> ReeReceipts:
        for name, receipt in self.experiments.items():
            if name != receipt.experiment_name:
                raise ValueError("experiment receipt key must equal receipt experiment_name")
        return self


OVERLAY_ENTRY = "overlay/"


class BundleEntry(_DomainModel):
    path: ReePath
    digest: Annotated[Digest, digest_of("file", ".", named_by="contents.entries[*].path")]
    size: int = Field(ge=0)


class BundleContents(_DomainModel):
    entries: tuple[BundleEntry, ...] = ()

    @model_validator(mode="after")
    def _canonical_entries(self) -> BundleContents:
        paths = [str(entry.path) for entry in self.entries]
        if paths != sorted(paths):
            raise ValueError("bundle entries must be sorted by path")
        if len(paths) != len(set(paths)):
            raise ValueError("bundle entry paths must be unique")
        if strays := [
            path for path in paths if path.startswith(OVERLAY_ENTRY) and not is_overlay_path(path[len(OVERLAY_ENTRY) :])
        ]:
            raise ValueError(f"an REE's overlay holds only its scripts, not {strays[0]}")
        return self


class CapturePolicy(_DomainModel):
    version: Literal[2] = 2
    lfs_paths: tuple[ReePath, ...] = ()

    @model_validator(mode="after")
    def _canonical_paths(self) -> CapturePolicy:
        paths = [str(path) for path in self.lfs_paths]
        if paths != sorted(set(paths)):
            raise ValueError("LFS paths must be unique and sorted")
        if any(part in {".git", "."} for path in paths for part in path.split("/")):
            raise ValueError("Unsafe LFS path")
        return self


class ReeSubject(_DomainModel):
    schema_version: Literal[1] = CURRENT_SCHEMA_VERSION
    definition: ReeDefinition
    receipts: ReeReceipts = Field(default_factory=ReeReceipts)
    contents: BundleContents = Field(default_factory=BundleContents)
    capture: CapturePolicy = Field(default_factory=CapturePolicy)


class ReeSeal(_DomainModel):
    sealed_at: UtcInstant
    ree_digest: Annotated[Digest, digest_of("subject")]


def canonical_subject_digest(subject: ReeSubject) -> Digest:
    return digest_json(
        {
            "domain": "org.repo2ree.ree-subject",
            "subject": subject.model_dump(mode="json", exclude_none=True),
        }
    )


class Ree(_DomainModel):
    subject: ReeSubject
    seal: ReeSeal | None = None

    @model_validator(mode="after")
    def _valid_seal(self) -> Ree:
        if self.seal is not None and self.seal.ree_digest != canonical_subject_digest(self.subject):
            raise ValueError("REE seal digest does not match its subject")
        return self


ReeStatus = Literal["draft", "sealed"]


def ree_status(ree: Ree) -> ReeStatus:
    return "sealed" if ree.seal is not None else "draft"


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "ActivateExperimentEnvironmentDefinition",
    "BundleContents",
    "BundleEntry",
    "CheckWorkingEnvironmentDefinition",
    "Contributor",
    "ExperimentDefinition",
    "ExperimentEnvironmentDefinition",
    "HardwareDefinition",
    "Ree",
    "ReeCatalogMetadata",
    "ReeDefinition",
    "ReeReceipts",
    "ReeSeal",
    "ReeStatus",
    "ReeSubject",
    "SourceDefinition",
    "canonical_subject_digest",
    "ree_status",
]
