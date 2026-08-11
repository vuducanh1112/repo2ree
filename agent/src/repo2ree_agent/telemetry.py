"""Safe, runtime-neutral telemetry facts for workbench operations."""

from __future__ import annotations

import hashlib

from repo2ree_protocol.agent import WorkbenchRef


def workbench_reference_hash(ref: WorkbenchRef) -> str:
    """Return a stable correlation key without exposing the opaque token."""
    material = f"{ref.runtime}\0{ref.token}".encode()
    return hashlib.sha256(material).hexdigest()[:16]
