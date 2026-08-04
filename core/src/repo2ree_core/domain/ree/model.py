"""The portable REE aggregate.

Only what an REE *is*: its declaration, the receipts that back it, the bundle
inventory, and the seal over all three. What that adds up to right now — which
evidence still holds and which the tree has moved out from under — is derived,
never stored, and lives in :mod:`repo2ree_core.domain.ree.audit`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from repo2ree_core.digests import digest_json
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.domain.primitives import Digest, ReePath, SourceType, UtcInstant, WorkspacePath
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    ObserveHardwareReceipt,
    RunExperimentReceipt,
    TestActivationReceipt,
)
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
    experiment_slug,
    experiment_verify_script_path,
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


class BuildRuntimeDefinition(_DomainModel):
    build_runtime_script_path: ReePath = ReePath(RESERVED_BUILD_SCRIPT)
    build_runtime_script_digest: Digest
    build_runtime_script_size: int = Field(ge=0)

    @field_validator("build_runtime_script_path")
    @classmethod
    def _fixed_path(cls, value: ReePath) -> ReePath:
        if value != RESERVED_BUILD_SCRIPT:
            raise ValueError(f"build runtime script path must be {RESERVED_BUILD_SCRIPT!r}")
        return value


class RuntimeDefinition(_DomainModel):
    runtime_path: WorkspacePath
    expected_runtime_digest: Digest | None = None


class TestActivationDefinition(_DomainModel):
    run_script_path: ReePath = ReePath(RESERVED_ACTIVATION_SCRIPT)
    run_script_digest: Digest
    run_script_size: int = Field(ge=0)
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    verify_script_size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _complete_scripts(self) -> TestActivationDefinition:
        if self.run_script_path != RESERVED_ACTIVATION_SCRIPT:
            raise ValueError(f"activation script path must be {RESERVED_ACTIVATION_SCRIPT!r}")
        verification = (self.verify_script_path, self.verify_script_digest, self.verify_script_size)
        if any(item is not None for item in verification) and not all(item is not None for item in verification):
            raise ValueError("activation verification path, digest, and size must be present together")
        if self.verify_script_path is not None and self.verify_script_path != RESERVED_ACTIVATION_VERIFY_SCRIPT:
            raise ValueError(f"activation verification path must be {RESERVED_ACTIVATION_VERIFY_SCRIPT!r}")
        return self


class ExperimentDefinition(_DomainModel):
    name: str = Field(min_length=1)
    run_script_path: ReePath
    run_script_digest: Digest
    run_script_size: int = Field(ge=0)
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    verify_script_size: int | None = Field(default=None, ge=0)
    output_paths: tuple[WorkspacePath, ...] = ()

    @model_validator(mode="after")
    def _conventional_paths(self) -> ExperimentDefinition:
        if self.run_script_path != experiment_run_script_path(self.name):
            raise ValueError("experiment run script path must be derived from its name")
        verification = (self.verify_script_path, self.verify_script_digest, self.verify_script_size)
        if any(item is not None for item in verification) and not all(item is not None for item in verification):
            raise ValueError("experiment verification path, digest, and size must be present together")
        if self.verify_script_path is not None and self.verify_script_path != experiment_verify_script_path(self.name):
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
    build_runtime: BuildRuntimeDefinition | None = None
    runtime: RuntimeDefinition | None = None
    test_activation: TestActivationDefinition | None = None
    hardware: HardwareDefinition | None = None
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
    source: AcquireSourceReceipt | None = None
    evaluation: EvaluateReproducibilityReceipt | None = None
    hardware_observation: ObserveHardwareReceipt | None = None
    build: BuildRuntimeReceipt | None = None
    sbom: GenerateSbomReceipt | None = None
    sbom_cross_check: CrossCheckSbomReceipt | None = None
    test_activation: TestActivationReceipt | None = None
    experiments: dict[str, RunExperimentReceipt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _experiment_keys_match(self) -> ReeReceipts:
        for name, receipt in self.experiments.items():
            if name != receipt.experiment_name:
                raise ValueError("experiment receipt key must equal receipt experiment_name")
        return self


class BundleEntry(_DomainModel):
    path: ReePath
    digest: Digest
    size: int = Field(ge=0)


class BundleContents(_DomainModel):
    """Inventory bound into a sealed bundle; persisted drafts keep this empty."""

    entries: tuple[BundleEntry, ...] = ()

    @model_validator(mode="after")
    def _canonical_entries(self) -> BundleContents:
        paths = [str(entry.path) for entry in self.entries]
        if paths != sorted(paths):
            raise ValueError("bundle entries must be sorted by path")
        if len(paths) != len(set(paths)):
            raise ValueError("bundle entry paths must be unique")
        return self


class ReeSubject(_DomainModel):
    schema_version: Literal[1] = CURRENT_SCHEMA_VERSION
    definition: ReeDefinition = Field(default_factory=ReeDefinition)
    receipts: ReeReceipts = Field(default_factory=ReeReceipts)
    contents: BundleContents = Field(default_factory=BundleContents)


class Signature(_DomainModel):
    algorithm: str = Field(min_length=1)
    verification_material: str = Field(min_length=1)
    value: str = Field(min_length=1)


class ReeSeal(_DomainModel):
    sealed_at: UtcInstant
    ree_digest: Digest
    signature: Signature | None = None


def canonical_subject_digest(subject: ReeSubject) -> Digest:
    return digest_json(
        {
            "domain": "org.repo2ree.ree-subject",
            "version": subject.schema_version,
            "subject": subject.model_dump(mode="json"),
        }
    )


class Ree(_DomainModel):
    subject: ReeSubject = Field(default_factory=ReeSubject)
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
    "BuildRuntimeDefinition",
    "BundleContents",
    "BundleEntry",
    "Contributor",
    "ExperimentDefinition",
    "HardwareDefinition",
    "Ree",
    "ReeCatalogMetadata",
    "ReeDefinition",
    "ReeReceipts",
    "ReeSeal",
    "ReeStatus",
    "ReeSubject",
    "RuntimeDefinition",
    "Signature",
    "SourceDefinition",
    "TestActivationDefinition",
    "canonical_subject_digest",
    "ree_status",
]
