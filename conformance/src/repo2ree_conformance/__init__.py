"""Behaviour specification and conformance checking for repo2ree.

The specification under ``specifications/behaviour`` declares entities with one
owner each, the boundaries between components, and cross-entity invariants.
Owners record their transitions in durable journals; this package checks those
journals, and the REE Git histories, against the specification.
"""

from repo2ree_conformance.check import CheckResult, check
from repo2ree_conformance.evidence import Event, Evidence, Source
from repo2ree_conformance.files import load_spec
from repo2ree_conformance.sources import load_evidence
from repo2ree_conformance.spec import Spec

__all__ = ["CheckResult", "Event", "Evidence", "Source", "Spec", "check", "load_evidence", "load_spec"]
