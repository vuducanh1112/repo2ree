"""Behaviour specification and conformance checking for repo2ree.

The specification under ``specifications/behaviour`` declares entities with one
owner each, the boundaries between components, and cross-entity invariants.
Owners record their transitions in durable journals; this package checks those
journals, and the REE Git histories, against the specification.
"""

from repo2ree_conformance.check import CheckResult, Judgement, Model, check, judge_occurrences, replay
from repo2ree_conformance.evidence import Event, Evidence, Source
from repo2ree_conformance.files import load_spec
from repo2ree_conformance.recording import load_recording
from repo2ree_conformance.sources import history_head, load_evidence
from repo2ree_conformance.spec import Spec
from repo2ree_conformance.verification import (
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
    "load_evidence",
    "load_recording",
    "load_spec",
    "read_verification",
    "replay",
    "verify",
]
