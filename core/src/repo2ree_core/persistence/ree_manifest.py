"""The one serialization of an REE, read and written wherever it appears.

There is a single REE document. The workbench keeps it at the REE root and a
bundle carries the same file at ``ree/ree.json`` — same name, same bytes, same
parser — so a bundle unpacked into a directory has already produced a readable
REE rather than a manifest that has to be copied into one.

That is why the encoding lives here rather than at either call site: two
spellings of one document is exactly the drift this module exists to prevent.
The bytes are indented and key-sorted because an REE is meant to be read by the
people auditing it and diffed between runs. They are deliberately *not* the
digest encoding — :func:`repo2ree_core.digests.digest_json` canonicalizes
compactly for hashing, and the seal digest is taken over the model rather than
over these bytes, so how this file is spelled can change without invalidating a
seal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.domain.ree.transitions import validate_seal
from repo2ree_core.persistence.files import json_document_bytes


def ree_manifest_payload(ree: Ree) -> dict[str, Any]:
    """The REE as JSON-ready data, seal checked before it is handed on."""
    validate_seal(ree)
    payload: dict[str, Any] = ree.model_dump(mode="json", exclude_none=True)
    return payload


def ree_manifest_bytes(ree: Ree) -> bytes:
    """The REE document's bytes, identical on disk and in a bundle."""
    return json_document_bytes(ree_manifest_payload(ree))


def parse_ree_manifest(payload: Mapping[str, Any]) -> Ree:
    """Parse the one supported REE serialization generation."""
    ree = Ree.model_validate(dict(payload))
    validate_seal(ree)
    return ree
