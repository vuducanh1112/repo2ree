"""Serialization of the portable REE manifest used locally and in bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.transitions import validate_seal


def build_manifest_payload(ree: Ree) -> dict[str, Any]:
    """Serialize exactly the aggregate persisted in ``.ree.json``."""
    validate_seal(ree)
    return ree.model_dump(mode="json", exclude_none=True)


def split_manifest_payload(payload: Mapping[str, Any]) -> Ree:
    """Parse the one supported REE serialization generation."""
    ree = Ree.model_validate(dict(payload))
    validate_seal(ree)
    return ree


def manifest_bytes(ree: Ree) -> bytes:
    """Canonical bytes embedded at ``ree/ree.json``."""
    return json.dumps(build_manifest_payload(ree), sort_keys=True, separators=(",", ":")).encode("utf-8")
