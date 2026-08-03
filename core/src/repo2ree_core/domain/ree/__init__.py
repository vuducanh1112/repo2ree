"""The portable REE aggregate and its domain vocabulary."""

from repo2ree_core.domain.primitives import SourceType

from .model import (
    BuildRuntimeDefinition,
    BundleContents,
    BundleEntry,
    Contributor,
    ExperimentDefinition,
    HardwareDefinition,
    Ree,
    ReeAssessment,
    ReeCatalogMetadata,
    ReeDefinition,
    ReeReceipts,
    ReeSeal,
    ReeSubject,
    RuntimeDefinition,
    SourceDefinition,
    StepAssessment,
    TestActivationDefinition,
)

__all__ = [
    "BuildRuntimeDefinition",
    "BundleContents",
    "BundleEntry",
    "Contributor",
    "ExperimentDefinition",
    "HardwareDefinition",
    "Ree",
    "ReeAssessment",
    "ReeCatalogMetadata",
    "ReeDefinition",
    "ReeReceipts",
    "ReeSeal",
    "ReeSubject",
    "RuntimeDefinition",
    "SourceDefinition",
    "SourceType",
    "StepAssessment",
    "TestActivationDefinition",
]
