"""Behaviour specification and conformance checking for repo2ree.

The specification under ``assurance/spec`` declares entities with one
owner each, the boundaries between components, and cross-entity invariants.
Owners record their transitions in durable journals; this package checks those
journals, and the REE Git histories, against the specification.
"""

from repo2ree_assurance_checker.check import CheckResult, Judgement, Model, check, judge_occurrences, replay
from repo2ree_assurance_checker.dossier import load_dossier
from repo2ree_assurance_checker.evidence import Event, Evidence, Source
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.sources import history_head, load_evidence
from repo2ree_assurance_checker.spec import Spec
from repo2ree_assurance_checker.verification import (
    ARTIFACT,
    Verification,
    VerifiedEntity,
    VerifiedExchange,
    VerifiedModel,
    read_verification,
    verify,
)

__all__ = [
    "ARTIFACT",
    "CheckResult",
    "Event",
    "Evidence",
    "Judgement",
    "Model",
    "Source",
    "Spec",
    "Verification",
    "VerifiedEntity",
    "VerifiedExchange",
    "VerifiedModel",
    "check",
    "history_head",
    "judge_occurrences",
    "load_dossier",
    "load_evidence",
    "load_spec",
    "read_verification",
    "replay",
    "verify",
]
