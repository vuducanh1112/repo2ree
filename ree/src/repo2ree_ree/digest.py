from __future__ import annotations

import hashlib
from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from repo2ree_ree.canonical import canonical_json

DIGEST_PREFIX = "sha256:"


# A canonical digest is ``sha256:`` followed by 64 lowercase hex chars. The
# whole receipt and audit vocabulary relies on this one shape being comparable
# across recorded and current values, so every producer asserts it on the way out.
_DIGEST_LEN = len(DIGEST_PREFIX) + 64


class Digest(str):
    """Nominal SHA-256 digest retaining its scalar JSON representation."""

    def __new__(cls, value: str) -> Self:
        text = str(value)
        if not text.startswith(DIGEST_PREFIX) or not text.removeprefix(DIGEST_PREFIX):
            raise ValueError("Digest must use the sha256:<value> form")
        return str.__new__(cls, text)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


def is_canonical_digest(digest: str) -> bool:
    return digest.startswith(DIGEST_PREFIX) and len(digest) == _DIGEST_LEN


def digest_bytes(data: bytes) -> Digest:
    digest = Digest(DIGEST_PREFIX + hashlib.sha256(data).hexdigest())

    # ── postcondition ──
    assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    # ───────────────────
    return digest


def digest_json(payload: Any) -> Digest:
    """Digest of a JSON value in its RFC 8785 canonical form (:mod:`repo2ree_ree.canonical`)."""
    return digest_bytes(canonical_json(payload))
