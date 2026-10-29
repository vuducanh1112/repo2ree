from __future__ import annotations

import hashlib
from typing import Any

from repo2ree_ree.canonical import canonical_json
from repo2ree_ree.scalar import StringValue

DIGEST_PREFIX = "sha256:"
_DIGEST_LEN = len(DIGEST_PREFIX) + 64


class Digest(StringValue):
    @classmethod
    def validate(cls, value: str) -> str:
        if not value.startswith(DIGEST_PREFIX) or not value.removeprefix(DIGEST_PREFIX):
            raise ValueError("Digest must use the sha256:<value> form")
        return value


def is_canonical_digest(digest: str) -> bool:
    return digest.startswith(DIGEST_PREFIX) and len(digest) == _DIGEST_LEN


def digest_bytes(data: bytes) -> Digest:
    digest = Digest(DIGEST_PREFIX + hashlib.sha256(data).hexdigest())
    assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    return digest


def digest_json(payload: Any) -> Digest:
    return digest_bytes(canonical_json(payload))
