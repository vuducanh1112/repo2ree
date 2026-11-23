from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from repo2ree_core.domain.ree.transitions import validate_seal
from repo2ree_core.persistence.files import json_document_bytes
from repo2ree_ree.model import Ree


def ree_manifest_payload(ree: Ree) -> dict[str, Any]:
    validate_seal(ree)
    payload: dict[str, Any] = ree.model_dump(mode="json", exclude_none=True)
    return payload


def ree_manifest_bytes(ree: Ree) -> bytes:
    return json_document_bytes(ree_manifest_payload(ree))


def parse_ree_manifest(payload: Mapping[str, Any]) -> Ree:
    ree = Ree.model_validate(dict(payload))
    validate_seal(ree)
    return ree
