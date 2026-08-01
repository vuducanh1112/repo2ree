"""Pure projections over the canonical REE data model."""

from __future__ import annotations

from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.domain.primitives import ArtifactPath, GitRevision, Swhid, WorkspacePath
from repo2ree_core.domain.receipt import RunReceipt, receipt_step_key
from repo2ree_core.domain.ree import (
    AuthoredFile,
    ExperimentScripts,
    ReeAssessment,
    ReeCapability,
    ReeDefinition,
    ReeEvidence,
    ReeScripts,
    RuntimeDefinition,
    SourceDefinition,
)
from repo2ree_core.domain.ree_intent import ReeCatalogMetadata
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT, RESERVED_BUILD_SCRIPT


def metadata_of(definition: ReeDefinition) -> ReeCatalogMetadata:
    return definition.intent.catalog_metadata


def name_of(definition: ReeDefinition) -> str:
    return definition.intent.name


def source_of(definition: ReeDefinition) -> SourceDefinition:
    intent = definition.intent
    return SourceDefinition(
        origin_url=intent.origin_url,
        source_type=intent.source_type,
        revision=GitRevision(intent.revision) if intent.revision else None,
        swhid=Swhid(intent.swhid) if intent.swhid else None,
    )


def runtime_of(definition: ReeDefinition) -> RuntimeDefinition:
    return RuntimeDefinition(
        artifact_path=WorkspacePath(definition.intent.runtime) if definition.intent.runtime else None,
        activation=definition.intent.activation,
        sbom_path=ArtifactPath(definition.intent.sbom) if definition.intent.sbom else None,
    )


def experiments_of(definition: ReeDefinition) -> tuple[Experiment, ...]:
    return tuple(definition.intent.experiments)


def scripts_of(definition: ReeDefinition) -> ReeScripts:
    by_path: dict[str, AuthoredFile] = {str(file.path): file for file in definition.files}
    claimed: set[str] = set()

    def claim(path: str) -> AuthoredFile | None:
        if not path:
            return None
        file = by_path.get(path)
        if file is not None:
            claimed.add(path)
        return file

    build = claim(RESERVED_BUILD_SCRIPT)
    activation_run = claim(definition.intent.activation.run_script or RESERVED_ACTIVATION_SCRIPT)
    activation_verify = claim(definition.intent.activation.verify_script)
    experiment_scripts = tuple(
        ExperimentScripts(
            experiment_name=experiment.name,
            run=claim(experiment.run_script),
            verify=claim(experiment.verify_script),
        )
        for experiment in definition.intent.experiments
    )
    return ReeScripts(
        build_runtime=build,
        activation_run=activation_run,
        activation_verify=activation_verify,
        experiments=experiment_scripts,
        other=tuple(file for file in definition.files if file.path not in claimed),
    )


def selected_receipt(evidence: ReeEvidence, step: str) -> RunReceipt | None:
    return next((receipt for receipt in evidence.selected if receipt_step_key(receipt) == step), None)


def capability_ready(capability: ReeCapability) -> bool:
    return capability.status in ("ready", "not_applicable")


def all_capabilities_ready(assessment: ReeAssessment) -> bool:
    return (
        capability_ready(assessment.source)
        and capability_ready(assessment.runtime)
        and capability_ready(assessment.activation)
        and all(capability_ready(item.capability) for item in assessment.experiments)
    )
