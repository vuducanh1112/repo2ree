"""The REE aggregate and its domain vocabulary.

Persistence adapters live in :mod:`repo2ree_core.persistence`; this package is
pure and answers what an REE is, how it changes, and what its evidence means.
"""

from .intent import Contributor, ReeCatalogMetadata, ReeIntent, SourceType
from .model import (
    AuthoredFile,
    Ree,
    ReeAssessment,
    ReeCapability,
    ReeDefinition,
    ReeEvidence,
    ReeIdentity,
    ReeScripts,
    Seal,
)
from .state import ReeLifecycleState, SourceAcquiredBy

__all__ = [
    "AuthoredFile",
    "Contributor",
    "Ree",
    "ReeAssessment",
    "ReeCapability",
    "ReeCatalogMetadata",
    "ReeDefinition",
    "ReeEvidence",
    "ReeIdentity",
    "ReeIntent",
    "ReeLifecycleState",
    "ReeScripts",
    "Seal",
    "SourceAcquiredBy",
    "SourceType",
]
